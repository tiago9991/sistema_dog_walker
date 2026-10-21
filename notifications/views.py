"""Notification views: personal list, mark-as-read actions and the JSON
poll endpoint (PRD RNF-004 — Sprint 11).

Notifications are personal to each user: every queryset is scoped to
``request.user`` — no Django model permission is involved, any
authenticated user manages only their own inbox (RF-013 scope rule).
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from notifications.models import Notification

# How many notifications a single poll may report (JS toasts them).
POLL_NEW_LIMIT = 10


class NotificationListView(LoginRequiredMixin, ListView):
    """The user's own notifications, newest first."""

    context_object_name = 'notifications'
    paginate_by = 20
    template_name = 'notifications/notification_list.html'

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['unread_count'] = (
            self.get_queryset().filter(is_read=False).count()
        )
        return context


def _back_or_list(request):
    """Return to the referring page when it is a safe internal URL."""
    target = request.POST.get('next')
    if target and url_has_allowed_host_and_scheme(
        target,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(target)
    return redirect('notifications:list')


@require_POST
@login_required
def notification_mark_read(request, pk):
    """Mark one notification as read (only the recipient's own)."""
    notification = get_object_or_404(
        Notification, pk=pk, recipient=request.user
    )
    notification.mark_read()
    return _back_or_list(request)


@require_POST
@login_required
def notifications_mark_all_read(request):
    """Mark every unread notification of the user as read."""
    updated = Notification.objects.filter(
        recipient=request.user, is_read=False
    ).update(is_read=True, read_at=timezone.now())
    if updated:
        messages.success(
            request,
            f'{updated} notificação(ões) marcada(s) como lida(s).',
        )
    return _back_or_list(request)


@login_required
def notifications_poll(request):
    """JSON endpoint polled by the interface (``static/js/scsi.js``).

    Without ``?after=<id>`` the response only reports the current state
    (the JS initializes its "last seen" marker without toasting). With
    ``?after=<id>`` the response also includes the unread notifications
    created after that id, which the interface shows as toasts
    (RNF-004: completion generates a notification in the interface).
    """
    queryset = Notification.objects.filter(recipient=request.user)

    raw_after = request.GET.get('after')
    after = None
    if raw_after is not None:
        try:
            after = int(raw_after)
        except ValueError:
            after = None

    unread = queryset.filter(is_read=False).count()
    latest_id = queryset.values_list('pk', flat=True).first() or 0

    fresh = []
    if after is not None:
        fresh = queryset.filter(pk__gt=after, is_read=False)[:POLL_NEW_LIMIT]

    return JsonResponse(
        {
            'unread': unread,
            'latest_id': latest_id,
            'new': [
                {
                    'id': notification.pk,
                    'level': notification.level,
                    'title': notification.title,
                    'message': notification.message,
                    'link': notification.link,
                    'created_at': timezone.localtime(notification.created_at)
                    .strftime('%d/%m/%Y %H:%M'),
                }
                for notification in fresh
            ],
        }
    )
