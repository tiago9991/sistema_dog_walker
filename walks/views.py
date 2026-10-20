"""Walk views: period lists (day/week/month/history — PRD RF-006/RF-009/RF-012)
and status actions (RF-007/RF-008)."""

from datetime import date, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.views.generic import ListView, RedirectView

from clients.models import Client
from dogs.models import Dog

from walks.models import Walk
from walks.services import transition_walk


def _valid_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _parse_iso_date(value):
    try:
        return date.fromisoformat(value or '')
    except ValueError:
        return None


def _parse_month(value):
    """``YYYY-MM`` → ``(year, month)`` or ``None``."""
    try:
        year, month = (int(part) for part in (value or '').split('-'))
        if 1 <= month <= 12:
            return year, month
    except (ValueError, TypeError):
        pass
    return None


def _month_bounds(year, month):
    start = date(year, month, 1)
    if month == 12:
        end = date(year, 12, 31)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start, end


def _shift_month(year, month, delta):
    total = year * 12 + (month - 1) + delta
    return total // 12, total % 12 + 1


class BaseWalkListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """Shared machinery for the day/week/month/history lists."""

    permission_required = 'walks.view_walk'
    template_name = 'walks/walk_list.html'
    context_object_name = 'walks'
    paginate_by = 30
    mode = 'day'
    url_name = 'walks:day'
    descending = False

    # --- request param parsing -------------------------------------------

    def parse_filters(self):
        self.client_id = _valid_int(self.request.GET.get('client'))
        self.dog_id = _valid_int(self.request.GET.get('dog'))
        self.status = self.request.GET.get('status', '')
        if self.status and self.status not in dict(Walk.STATUS_CHOICES):
            self.status = ''

    # --- period hooks (implemented per mode) ------------------------------

    def get_period(self):
        """Return ``(start, end)`` dates (either may be ``None``)."""
        raise NotImplementedError

    def period_context(self):
        return {}

    def nav_urls(self):
        return None

    def url_for(self, **params):
        base = {
            key: value
            for key, value in (
                ('client', self.client_id),
                ('dog', self.dog_id),
                ('status', self.status),
            )
            if value
        }
        base.update({k: v for k, v in params.items() if v})
        url = reverse(self.url_name)
        return f'{url}?{urlencode(base)}' if base else url

    # --- queryset ---------------------------------------------------------

    def get_queryset(self):
        self.parse_filters()
        start, end = self.get_period()
        queryset = Walk.objects.select_related('dog', 'dog__client')
        if start:
            queryset = queryset.filter(date__gte=start)
        if end:
            queryset = queryset.filter(date__lte=end)
        if self.client_id:
            queryset = queryset.filter(dog__client_id=self.client_id)
        if self.dog_id:
            queryset = queryset.filter(dog_id=self.dog_id)
        if self.status:
            queryset = queryset.filter(status=self.status)
        ordering = ('-date', '-dog__name') if self.descending else ('date', 'dog__name')
        return queryset.order_by(*ordering)

    # --- context ----------------------------------------------------------

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop('page', None)
        context.update(
            {
                'mode': self.mode,
                'mode_url': reverse(self.url_name),
                'status_choices': Walk.STATUS_CHOICES,
                'current_client_id': self.client_id,
                'current_dog_id': self.dog_id,
                'current_status': self.status,
                'current_date': self.request.GET.get('date', ''),
                'current_month': self.request.GET.get('month', ''),
                'clients': Client.objects.order_by('name'),
                'dogs': self.get_dog_choices(),
                'nav': self.nav_urls(),
                'querystring': params.urlencode(),
            }
        )
        context.update(self.period_context())
        return context

    def get_dog_choices(self):
        queryset = Dog.objects.select_related('client').order_by('client__name', 'name')
        if self.client_id:
            queryset = queryset.filter(client_id=self.client_id)
        return queryset


class WalkDayListView(BaseWalkListView):
    mode = 'day'
    url_name = 'walks:day'

    def get_period(self):
        self.day = _parse_iso_date(self.request.GET.get('date')) or timezone.localdate()
        return self.day, self.day

    def period_context(self):
        return {
            'period_start': self.day,
            'period_end': self.day,
            'current_date': self.day.isoformat(),
        }

    def nav_urls(self):
        return {
            'prev': self.url_for(date=(self.day - timedelta(days=1)).isoformat()),
            'next': self.url_for(date=(self.day + timedelta(days=1)).isoformat()),
        }


class WalkWeekListView(BaseWalkListView):
    mode = 'week'
    url_name = 'walks:week'

    def get_period(self):
        reference = (
            _parse_iso_date(self.request.GET.get('date')) or timezone.localdate()
        )
        self.period = (
            reference - timedelta(days=reference.weekday()),
            reference - timedelta(days=reference.weekday()) + timedelta(days=6),
        )
        return self.period

    def period_context(self):
        return {
            'period_start': self.period[0],
            'period_end': self.period[1],
            # The filter input anchors on the week's Monday.
            'current_date': self.period[0].isoformat(),
        }

    def nav_urls(self):
        return {
            'prev': self.url_for(
                date=(self.period[0] - timedelta(days=7)).isoformat()
            ),
            'next': self.url_for(
                date=(self.period[0] + timedelta(days=7)).isoformat()
            ),
        }


class WalkMonthListView(BaseWalkListView):
    mode = 'month'
    url_name = 'walks:month'

    def get_period(self):
        parsed = _parse_month(self.request.GET.get('month'))
        if parsed is None:
            today = timezone.localdate()
            parsed = (today.year, today.month)
        self.month = parsed
        return _month_bounds(*parsed)

    def period_context(self):
        start, end = _month_bounds(*self.month)
        return {
            'period_start': start,
            'period_end': end,
            'current_month': f'{self.month[0]:04d}-{self.month[1]:02d}',
        }

    def nav_urls(self):
        prev_year, prev_month = _shift_month(*self.month, delta=-1)
        next_year, next_month = _shift_month(*self.month, delta=1)
        return {
            'prev': self.url_for(month=f'{prev_year:04d}-{prev_month:02d}'),
            'next': self.url_for(month=f'{next_year:04d}-{next_month:02d}'),
        }


class WalkHistoryListView(BaseWalkListView):
    """Full walk history with filters (PRD RF-009). Newest first."""

    mode = 'history'
    url_name = 'walks:history'
    descending = True

    def get_period(self):
        parsed = _parse_month(self.request.GET.get('month'))
        if parsed is None:
            return None, None
        return _month_bounds(*parsed)

    def period_context(self):
        parsed = _parse_month(self.request.GET.get('month'))
        if parsed is None:
            return {}
        year, month = parsed
        return {'period_start': date(year, month, 1), 'current_month': f'{year:04d}-{month:02d}'}


# --- status actions (RF-007/RF-008) ---------------------------------------


def _get_walk(pk):
    return get_object_or_404(
        Walk.objects.select_related('dog', 'dog__client'), pk=pk
    )


def _redirect_back(request, fallback='walks:day'):
    target = request.POST.get('next') or request.GET.get('next')
    if target and url_has_allowed_host_and_scheme(
        target,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(target)
    return redirect(fallback)


def _transition(request, walk, to_status, observation=None):
    try:
        transition_walk(walk, to_status, observation=observation)
    except ValidationError as exc:
        messages.error(request, exc.messages[0] if exc.messages else str(exc))
    else:
        messages.success(
            request,
            f'Passeio de {walk.dog.name} em {walk.date:%d/%m/%Y} '
            f'atualizado para "{walk.get_status_display()}".',
        )


@require_POST
@login_required
@permission_required('walks.change_walk', raise_exception=True)
def walk_complete(request, pk):
    """RF-007: mark a walk as completed."""
    walk = _get_walk(pk)
    _transition(request, walk, Walk.STATUS_COMPLETED)
    return _redirect_back(request)


@require_POST
@login_required
@permission_required('walks.change_walk', raise_exception=True)
def walk_revert(request, pk):
    """Revert a walk back to 'previsto' (correcting mistakes)."""
    walk = _get_walk(pk)
    _transition(request, walk, Walk.STATUS_SCHEDULED)
    return _redirect_back(request)


@login_required
@permission_required('walks.change_walk', raise_exception=True)
def walk_cancel(request, pk):
    """RF-008: cancel a walk, with an optional reason."""
    walk = _get_walk(pk)
    if request.method == 'POST':
        _transition(
            request,
            walk,
            Walk.STATUS_CANCELLED,
            observation=request.POST.get('observation', ''),
        )
        return _redirect_back(request)
    return render(
        request,
        'walks/walk_action_form.html',
        {
            'walk': walk,
            'action': 'cancel',
            'next': request.GET.get('next', ''),
            'title': 'Cancelar passeio',
            'confirm_label': 'Cancelar passeio',
            'confirm_class': 'btn-danger',
        },
    )


@login_required
@permission_required('walks.change_walk', raise_exception=True)
def walk_miss(request, pk):
    """RF-008: register a walk as not performed, with an optional reason."""
    walk = _get_walk(pk)
    if request.method == 'POST':
        _transition(
            request,
            walk,
            Walk.STATUS_MISSED,
            observation=request.POST.get('observation', ''),
        )
        return _redirect_back(request)
    return render(
        request,
        'walks/walk_action_form.html',
        {
            'walk': walk,
            'action': 'miss',
            'next': request.GET.get('next', ''),
            'title': 'Registrar passeio não realizado',
            'confirm_label': 'Registrar não realizado',
            'confirm_class': 'btn-warning',
        },
    )
