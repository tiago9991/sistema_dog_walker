"""Operational dashboard (PRD RF-010 — Sprint 10).

Home page of the application (``/``): a decision-oriented summary with
entity counts, today's walks, and the current month's indicators (RF-011
counters), filterable by month and client.

Indicators (registered in PRD RF-010):

- clients: active/total;
- dogs: active/total;
- today: walks by status (previstos/realizados/cancelados/não realizados);
- month (RF-011 counters): contratados/previstos/realizados/cancelados/
  não realizados/restantes, per client and overall.

All counters come from aggregate queries (no per-row queries — RNF-003;
the monthly counters reuse ``walks.services.monthly_control``).
"""

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Count, Q
from django.utils import timezone
from django.views.generic import TemplateView

from clients.models import Client
from dogs.models import Dog

from walks.models import Walk
from walks.services import (
    month_bounds,
    monthly_control,
    group_monthly_control_by_client,
    parse_month,
)


def _valid_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _progress(part, total):
    return round(100 * part / total) if total else 0


class DashboardView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """RF-010 operational summary (Sprint 10)."""

    permission_required = (
        'clients.view_client',
        'dogs.view_dog',
        'walks.view_walk',
    )
    template_name = 'dashboard/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        today = timezone.localdate()
        parsed = parse_month(self.request.GET.get('month'))
        if parsed is None:
            parsed = (today.year, today.month)
        year, month = parsed
        month_start, month_end = month_bounds(year, month)

        client = Client.objects.filter(
            pk=_valid_int(self.request.GET.get('client'))
        ).first()

        # --- entities ----------------------------------------------------
        client_stats = Client.objects.aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(is_active=True)),
        )
        dog_stats = Dog.objects.aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(is_active=True)),
        )

        # --- today (RF-010: previstos/realizados/restantes do dia) -------
        today_stats = Walk.objects.filter(date=today).aggregate(
            total=Count('id'),
            scheduled=Count('id', filter=Q(status=Walk.STATUS_SCHEDULED)),
            completed=Count('id', filter=Q(status=Walk.STATUS_COMPLETED)),
            cancelled=Count('id', filter=Q(status=Walk.STATUS_CANCELLED)),
            missed=Count('id', filter=Q(status=Walk.STATUS_MISSED)),
        )
        today_walks = Walk.objects.select_related('dog', 'dog__client').filter(
            date=today
        )
        if client is not None:
            today_walks = today_walks.filter(dog__client=client)
        today_walks = today_walks.order_by('dog__name')

        # --- month (RF-011 counters, reused) ------------------------------
        rows, month_totals = monthly_control(
            month_start, month_end, client=client
        )
        client_groups = group_monthly_control_by_client(rows)

        context.update(
            {
                'today': today,
                # Entities
                'clients_active': client_stats['active'],
                'clients_total': client_stats['total'],
                'clients_inactive': client_stats['total'] - client_stats['active'],
                'clients_progress': _progress(
                    client_stats['active'], client_stats['total']
                ),
                'dogs_active': dog_stats['active'],
                'dogs_total': dog_stats['total'],
                'dogs_inactive': dog_stats['total'] - dog_stats['active'],
                'dogs_progress': _progress(dog_stats['active'], dog_stats['total']),
                # Today
                'today_stats': today_stats,
                'today_remaining': today_stats['scheduled'],
                'today_progress': _progress(
                    today_stats['completed'], today_stats['total']
                ),
                'today_walks': today_walks,
                # Month (RF-011)
                'period_start': month_start,
                'period_end': month_end,
                'current_month': f'{year:04d}-{month:02d}',
                'month_totals': month_totals,
                'client_groups': client_groups,
                # Filters
                'clients': Client.objects.order_by('name'),
                'current_client_id': client.pk if client else 0,
            }
        )
        return context
