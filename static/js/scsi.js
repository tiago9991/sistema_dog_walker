/* Project script (Sprint 11 — PRD RNF-004): background task dispatch with
 * loading feedback and notification polling with toasts.
 *
 * - Forms with [data-async-task] are submitted via fetch: the page never
 *   navigates away, the submit button shows a loading spinner until the
 *   task's completion notification arrives (RNF-004 steps 1-3).
 * - The poller hits /notifications/poll/ every 30s (and every 4s while a
 *   task is pending): new unread notifications become toasts and update
 *   the header badge (RNF-004 step 4). "Last seen" is kept per tab
 *   (sessionStorage) so navigating does not re-toast old notifications.
 * Requires the design system bundle (Bootstrap Toast) — degrades
 * silently (badge only) if unavailable. */
(function () {
    'use strict';

    var LAST_SEEN_KEY = 'scsi.notifications.lastSeen';
    var POLL_INTERVAL_MS = 30000;
    var FAST_POLL_INTERVAL_MS = 4000;
    var FAST_POLL_MAX_TRIES = 45; /* ~3 minutes */
    var TOAST_DELAY_MS = 8000;

    /* ---------- helpers ------------------------------------------------ */

    function lastSeen() {
        var value = parseInt(sessionStorage.getItem(LAST_SEEN_KEY) || '', 10);
        return isNaN(value) ? 0 : value;
    }

    function setLastSeen(value) {
        sessionStorage.setItem(LAST_SEEN_KEY, String(value));
    }

    function hasLastSeen() {
        return sessionStorage.getItem(LAST_SEEN_KEY) !== null;
    }

    function csrfToken() {
        var parts = (document.cookie || '').split('; ');
        for (var i = 0; i < parts.length; i += 1) {
            var pair = parts[i].split('=');
            if (pair[0] === 'csrftoken') {
                return decodeURIComponent(pair.slice(1).join('='));
            }
        }
        return '';
    }

    function escapeHtml(value) {
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(value == null ? '' : String(value)));
        return div.innerHTML;
    }

    function levelVisuals(level) {
        switch (level) {
        case 'success':
            return { classes: 'bg-soft-success text-success', icon: 'feather-check-circle' };
        case 'error':
            return { classes: 'bg-soft-danger text-danger', icon: 'feather-alert-circle' };
        case 'warning':
            return { classes: 'bg-soft-warning text-warning', icon: 'feather-alert-triangle' };
        default:
            return { classes: 'bg-soft-info text-info', icon: 'feather-bell' };
        }
    }

    /* ---------- toasts (design system: Bootstrap 5 toasts) ------------- */

    function showToast(title, message, level, when) {
        var container = document.getElementById('scsi-toasts');
        if (!container) return;
        var visuals = levelVisuals(level);
        var element = document.createElement('div');
        element.className = 'toast';
        element.setAttribute('role', 'alert');
        element.setAttribute('aria-live', 'assertive');
        element.setAttribute('aria-atomic', 'true');
        element.innerHTML =
            '<div class="toast-header">' +
            '<span class="avatar-text avatar-xs ' + visuals.classes + ' me-2">' +
            '<i class="' + visuals.icon + '"></i></span>' +
            '<strong class="me-auto fs-12">' + escapeHtml(title) + '</strong>' +
            (when ? '<small class="text-muted fs-11">' + escapeHtml(when) + '</small>' : '') +
            '<button type="button" class="btn-close" data-bs-dismiss="toast" ' +
            'aria-label="Fechar"></button>' +
            '</div>' +
            (message ? '<div class="toast-body fs-12">' + escapeHtml(message) + '</div>' : '');
        container.appendChild(element);
        if (window.bootstrap && window.bootstrap.Toast) {
            var toast = new window.bootstrap.Toast(element, { delay: TOAST_DELAY_MS });
            element.addEventListener('hidden.bs.toast', function () { element.remove(); });
            toast.show();
        } else {
            /* Fallback without the JS bundle: visible for a few seconds. */
            element.classList.add('show');
            window.setTimeout(function () { element.remove(); }, TOAST_DELAY_MS);
        }
    }

    /* ---------- header badge ------------------------------------------- */

    function updateBadge(unread) {
        var badge = document.querySelector('[data-notifications-badge]');
        if (!badge) return;
        badge.textContent = String(unread);
        if (unread > 0) {
            badge.removeAttribute('hidden');
        } else {
            badge.setAttribute('hidden', 'hidden');
        }
    }

    /* ---------- poller -------------------------------------------------- */

    var pendingTasks = 0;

    function poll() {
        var url = '/notifications/poll/';
        if (hasLastSeen()) {
            url += '?after=' + lastSeen();
        }
        return fetch(url, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        }).then(function (response) {
            return response.ok ? response.json() : null;
        }).then(function (data) {
            if (!data) return;
            setLastSeen(Math.max(lastSeen(), data.latest_id || 0));
            updateBadge(data.unread || 0);
            var items = data.new || [];
            for (var i = 0; i < items.length; i += 1) {
                var notification = items[i];
                showToast(
                    notification.title,
                    notification.message,
                    notification.level,
                    notification.created_at
                );
            }
            if (items.length > 0 && pendingTasks > 0) {
                resetPendingTasks();
            }
        }).catch(function () { /* offline — the next poll retries */ });
    }

    /* ---------- async task dispatch (RNF-004 steps 1-3) ----------------- */

    function setButtonLoading(button) {
        if (button.dataset.originalHtml) return;
        button.dataset.originalHtml = button.innerHTML;
        button.disabled = true;
        button.classList.add('disabled');
        button.innerHTML =
            '<span class="spinner-border spinner-border-sm me-1" role="status" ' +
            'aria-hidden="true"></span><span>Executando…</span>';
    }

    function restoreButton(button) {
        if (!button.dataset.originalHtml) return;
        button.innerHTML = button.dataset.originalHtml;
        button.disabled = false;
        button.classList.remove('disabled');
        delete button.dataset.originalHtml;
    }

    function resetPendingTasks() {
        pendingTasks = 0;
        document.querySelectorAll('form[data-async-task]').forEach(function (form) {
            form.querySelectorAll('button[type="submit"]').forEach(restoreButton);
        });
    }

    function fastPoll() {
        var tries = 0;
        var timer = setInterval(function () {
            tries += 1;
            if (pendingTasks === 0 || tries > FAST_POLL_MAX_TRIES) {
                clearInterval(timer);
                if (pendingTasks > 0) {
                    resetPendingTasks();
                    showToast(
                        'Ainda aguardando a tarefa',
                        'A tarefa continua em execução em segundo plano — a notificação ' +
                        'de conclusão aparecerá aqui e no sino de notificações.',
                        'info',
                        ''
                    );
                }
                return;
            }
            poll();
        }, FAST_POLL_INTERVAL_MS);
    }

    document.addEventListener('submit', function (event) {
        var form = event.target;
        if (!(form instanceof HTMLFormElement)) return;
        if (!form.hasAttribute('data-async-task')) return;
        event.preventDefault();

        var button = form.querySelector('button[type="submit"]');
        if (button) setButtonLoading(button);
        pendingTasks += 1;

        fetch(form.action || window.location.href, {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrfToken()
            },
            body: new FormData(form),
            credentials: 'same-origin'
        }).then(function (response) {
            return response.json().then(function (data) {
                return { ok: response.ok, data: data };
            });
        }).then(function (result) {
            if (!result.ok) {
                pendingTasks -= 1;
                if (button) restoreButton(button);
                showToast(
                    'Falha ao iniciar a tarefa',
                    result.data && result.data.error
                        ? result.data.error
                        : 'Não foi possível iniciar a tarefa em segundo plano.',
                    'error',
                    ''
                );
                return;
            }
            /* Dispatched: keep the loading state until the completion
             * notification arrives (polling accelerates meanwhile). */
            return poll().then(fastPoll);
        }).catch(function () {
            pendingTasks -= 1;
            if (button) restoreButton(button);
            showToast('Falha na requisição', 'Não foi possível iniciar a tarefa.', 'error', '');
        });
    });

    /* ---------- boot ---------------------------------------------------- */

    document.addEventListener('DOMContentLoaded', function () {
        if (!document.querySelector('[data-notifications-badge]')) return;
        poll();
        setInterval(poll, POLL_INTERVAL_MS);
    });
})();
