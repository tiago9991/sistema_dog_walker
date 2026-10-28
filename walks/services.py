"""Walk generation, status transition and monthly control services.

Implements PRD RF-005 (deterministic, idempotent generation),
RF-006 (state machine), RF-007/RF-008 (transitions with observations)
and RF-011 (monthly control counters).

Rules registered in the PRD (section 53, resolved):

- generation window (item 9): ``[today - 7 days, today + 30 days]``
  (defaults, overridable per run); the lookback covers generation runs
  that did not happen (e.g. the machine was off) without creating walks
  older than the schedule itself;
- schedule changes (item 10): resynchronizes the dog's walks — future
  ``previsto`` walks are deleted and regenerated from the dog's active
  schedules; walks with any other status are preserved (history is never
  destroyed). The resync window reaches back to the earliest active
  schedule's own start (decision 2026-10-26, PRD section 53): a schedule
  registered after its start date still gets its past contracted walks,
  which the regular window (item 9) would miss;
- monthly ``restantes`` (item 7, resolved in Sprint 9):
  ``contratados - realizados - cancelados - não realizados`` (never
  negative). The rule per status (operational balance only — the
  financial impact of cancellations remains an open decision):
  ``realizado``/``não realizado``/``cancelado`` consume the month's
  contract; ``previsto`` stays pending; contracted dates without a
  generated walk (beyond the generation window) remain in the balance;
- contracted by monthly package (decision 2026-10-26 — PRD RF-011):
  ``Dog.monthly_walks_quota`` (e.g. 15 walks/month, flexible days) is
  the month's contract, replacing the weekday-calendar derivation —
  quantity packages cannot be expressed by recurrence alone.
"""

from datetime import date, timedelta
from itertools import groupby

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Min, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from dogs.models import Dog
from scheduling.models import WalkSchedule

from walks.models import Walk

# Monthly control counters (PRD RF-011) — order used by the views/templates.
MONTHLY_COUNTERS = (
    'contracted',
    'scheduled',
    'completed',
    'cancelled',
    'missed',
    'remaining',
)

# date.weekday() → schedule boolean field.
WEEKDAY_FIELD_BY_INDEX = {
    0: 'monday',
    1: 'tuesday',
    2: 'wednesday',
    3: 'thursday',
    4: 'friday',
    5: 'saturday',
    6: 'sunday',
}

GENERATION_LOOKBACK_DAYS = 7
GENERATION_HORIZON_DAYS = 30

# PRD RF-006 state machine: 'previsto' → done states; done states → 'previsto'
# (revert allows correcting mistakes; no other transitions exist).
ALLOWED_TRANSITIONS = {
    Walk.STATUS_SCHEDULED: {
        Walk.STATUS_COMPLETED,
        Walk.STATUS_CANCELLED,
        Walk.STATUS_MISSED,
    },
    Walk.STATUS_COMPLETED: {Walk.STATUS_SCHEDULED},
    Walk.STATUS_CANCELLED: {Walk.STATUS_SCHEDULED},
    Walk.STATUS_MISSED: {Walk.STATUS_SCHEDULED},
}


def generation_window(today=None, lookback_days=None, horizon_days=None):
    """Window bounds ``(start, end)`` for a generation run."""
    today = today or timezone.localdate()
    lookback = GENERATION_LOOKBACK_DAYS if lookback_days is None else lookback_days
    horizon = GENERATION_HORIZON_DAYS if horizon_days is None else horizon_days
    return today - timedelta(days=lookback), today + timedelta(days=horizon)


def active_schedules(dog=None, client=None):
    """Active schedules of operationally active dogs/clients."""
    queryset = (
        WalkSchedule.objects.select_related('dog', 'dog__client')
        .filter(
            is_active=True,
            dog__is_active=True,
            dog__client__is_active=True,
        )
        .order_by('dog__name', 'start_date')
    )
    if dog is not None:
        queryset = queryset.filter(dog=dog)
    if client is not None:
        queryset = queryset.filter(dog__client=client)
    return queryset


def generate_walks(
    today=None, lookback_days=None, horizon_days=None, dog=None
):
    """Generate ``previsto`` walks for every active schedule in the window.

    Deterministic and idempotent: each (dog, date) is created at most once —
    existing walks (any status) are kept untouched, backed by the
    ``(dog, date)`` unique constraint (PRD RF-005/section 10).
    """
    today = today or timezone.localdate()
    start, end = generation_window(today, lookback_days, horizon_days)

    stats = {'schedules': 0, 'created': 0, 'existing': 0}
    for schedule in active_schedules(dog=dog):
        stats['schedules'] += 1

        current = max(schedule.start_date, start)
        stop = end if schedule.end_date is None else min(schedule.end_date, end)
        if current > stop:
            continue

        for offset in range((stop - current).days + 1):
            date = current + timedelta(days=offset)
            if not getattr(schedule, WEEKDAY_FIELD_BY_INDEX[date.weekday()]):
                continue
            _, created = Walk.objects.get_or_create(
                dog=schedule.dog,
                date=date,
                defaults={'status': Walk.STATUS_SCHEDULED},
            )
            if created:
                stats['created'] += 1
            else:
                stats['existing'] += 1
    return stats


def resync_dog_walks(dog, today=None):
    """Reapply the dog's active schedules to its ``previsto`` walks.

    Deletes the dog's future ``previsto`` walks and regenerates them from
    the dog's active schedules. The window's lower bound is extended to
    the earliest active schedule's start when it is older than the
    standard lookback (decision 2026-10-26 — PRD section 53): a schedule
    registered after its own start date must still get its past
    contracted walks, so they can receive an outcome (RF-007/RF-008) and
    reach the monthly control/report. Per-schedule clamping in
    ``generate_walks`` still guarantees no walk older than the schedule
    itself. Walks with any other status are preserved (history is never
    destroyed — PRD RF-007/RF-009).
    """
    today = today or timezone.localdate()
    earliest_start = active_schedules(dog=dog).aggregate(
        earliest=Min('start_date')
    )['earliest']
    lookback = GENERATION_LOOKBACK_DAYS
    if earliest_start is not None:
        # Backdated schedules: never less than the default lookback (missed
        # runs), extended to the schedule's own start (never beyond it —
        # generate_walks clamps per schedule).
        lookback = max(GENERATION_LOOKBACK_DAYS, (today - earliest_start).days)
    with transaction.atomic():
        Walk.objects.filter(
            dog=dog, date__gte=today, status=Walk.STATUS_SCHEDULED
        ).delete()
        return generate_walks(today=today, dog=dog, lookback_days=lookback)


def transition_walk(walk, to_status, observation=None):
    """Validate and apply a status transition (PRD RF-006/007/008).

    Raises ``ValidationError`` for transitions outside the state machine.
    An optional observation is appended to ``notes`` with a timestamp, so
    the change stays registered (RF-007).
    """
    if to_status not in ALLOWED_TRANSITIONS.get(walk.status, set()):
        raise ValidationError(
            _(
                'Transição de status inválida: %(from)s → %(to)s.'
            )
            % {
                'from': walk.get_status_display(),
                'to': dict(Walk.STATUS_CHOICES).get(to_status, to_status),
            }
        )

    with transaction.atomic():
        walk.status = to_status
        walk.status_changed_at = timezone.now()
        observation = (observation or '').strip()
        if observation:
            timestamp = timezone.localtime().strftime('%d/%m/%Y %H:%M')
            entry = f'[{timestamp}] {walk.get_status_display()}: {observation}'
            walk.notes = f'{walk.notes}\n{entry}' if walk.notes else entry
        walk.save(
            update_fields=('status', 'status_changed_at', 'notes', 'updated_at')
        )
    return walk


# --- monthly control (PRD RF-011 — Sprint 9) --------------------------------


def parse_month(value):
    """``YYYY-MM`` → ``(year, month)`` or ``None`` for invalid/empty input."""
    try:
        year, month = (int(part) for part in (value or '').split('-'))
        if 1 <= month <= 12:
            return year, month
    except (ValueError, TypeError):
        pass
    return None


def month_bounds(year, month):
    """Calendar-month ``(start, end)`` dates (inclusive end)."""
    start = date(year, month, 1)
    if month == 12:
        end = date(year, 12, 31)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start, end


def shift_month(year, month, delta):
    """``(year, month)`` shifted by ``delta`` months (delta may be negative)."""
    total = year * 12 + (month - 1) + delta
    return total // 12, total % 12 + 1


def contracted_walks_by_dog(month_start, month_end, client=None, dog=None):
    """Contracted walks per dog id for the month (PRD RF-011).

    Two sources, in priority order (decision 2026-10-26 — PRD RF-011):

    1. the dog's ``monthly_walks_quota`` (monthly package by quantity,
       e.g. 15 walks with flexible days): the quota **is** the month's
       contract. Quantity packages cannot be expressed by weekday
       recurrence — 3 fixed days/week yields 13-15+ dates depending on
       the month, which misleads the client-facing control/report;
    2. otherwise, deterministic from the dog's active schedules (RF-004):
       a date of the month is contracted when an active schedule (of an
       operationally active dog/client) selects its weekday within the
       schedule period. Independent from the generation window, so it
       also covers months whose walks have not been generated yet.

    v1 limitation (registered in the PRD): the quota is a fixed per-dog
    value — for partial months (schedule starting/ending mid-month,
    deactivations) leave it empty or adjust it; the calendar derivation
    applies otherwise. Inactive dogs/clients never have a contract.
    """
    quota_counts = {}
    dogs_queryset = Dog.objects.filter(
        monthly_walks_quota__isnull=False,
        is_active=True,
        client__is_active=True,
    )
    if client is not None:
        dogs_queryset = dogs_queryset.filter(client=client)
    if dog is not None:
        dogs_queryset = dogs_queryset.filter(pk=dog.pk)
    for dog_id, quota in dogs_queryset.values_list('pk', 'monthly_walks_quota'):
        quota_counts[dog_id] = quota

    counts = dict(quota_counts)
    for schedule in active_schedules(client=client, dog=dog):
        if schedule.dog_id in quota_counts:
            continue  # the quota replaced the calendar derivation
        current = max(schedule.start_date, month_start)
        stop = month_end if schedule.end_date is None else min(
            schedule.end_date, month_end
        )
        if current > stop:
            continue
        for offset in range((stop - current).days + 1):
            month_date = current + timedelta(days=offset)
            if getattr(schedule, WEEKDAY_FIELD_BY_INDEX[month_date.weekday()]):
                counts[schedule.dog_id] = counts.get(schedule.dog_id, 0) + 1
    return counts


def monthly_control(month_start, month_end, client=None, dog=None):
    """Monthly control rows per dog (PRD RF-011) + overall totals.

    One row per dog that either has walks in the month or has contracted
    dates in the month (schedule-derived or via ``monthly_walks_quota``).
    ``remaining`` follows the Sprint 9 rule registered in the PRD (see
    the module docstring). Aggregate queries only (schedules, quota dogs
    and walks by status) plus one dog query — no per-row queries
    (RNF-003).
    """
    contracted = contracted_walks_by_dog(
        month_start, month_end, client=client, dog=dog
    )

    walk_counts = {
        entry['dog_id']: entry
        for entry in Walk.objects.filter(
            date__gte=month_start, date__lte=month_end
        )
        .values('dog_id')
        .annotate(
            scheduled=Count('id', filter=Q(status=Walk.STATUS_SCHEDULED)),
            completed=Count('id', filter=Q(status=Walk.STATUS_COMPLETED)),
            cancelled=Count('id', filter=Q(status=Walk.STATUS_CANCELLED)),
            missed=Count('id', filter=Q(status=Walk.STATUS_MISSED)),
        )
    }

    dog_ids = set(contracted) | set(walk_counts)
    if not dog_ids:
        return [], {counter: 0 for counter in MONTHLY_COUNTERS}

    dogs = (
        Dog.objects.select_related('client')
        .filter(pk__in=dog_ids)
        .order_by('client__name', 'name')
    )
    if client is not None:
        dogs = dogs.filter(client=client)
    if dog is not None:
        dogs = dogs.filter(pk=dog.pk)

    rows = []
    for dog_row in dogs:
        counts = walk_counts.get(dog_row.pk, {})
        completed = counts.get('completed', 0)
        cancelled = counts.get('cancelled', 0)
        missed = counts.get('missed', 0)
        contracted_count = contracted.get(dog_row.pk, 0)
        row = {
            'dog': dog_row,
            'client': dog_row.client,
            'contracted': contracted_count,
            'scheduled': counts.get('scheduled', 0),
            'completed': completed,
            'cancelled': cancelled,
            'missed': missed,
            'remaining': max(
                0, contracted_count - completed - cancelled - missed
            ),
        }
        row['progress'] = (
            round(100 * completed / contracted_count)
            if contracted_count
            else 0
        )
        rows.append(row)

    totals = {
        counter: sum(row[counter] for row in rows)
        for counter in MONTHLY_COUNTERS
    }
    totals['progress'] = (
        round(100 * totals['completed'] / totals['contracted'])
        if totals['contracted']
        else 0
    )
    return rows, totals


def completed_walk_dates_by_dog(month_start, month_end, client=None, dog=None):
    """Chronological ``realizado`` walk dates of the month, per dog id.

    Companion to ``monthly_control`` (RF-011) used by the monthly control
    PDF (PRD section 21) to list the days each dog was actually walked —
    recorded facts (``Walk.date``/``status``), not a derived rule. One
    aggregate query (``walk_status_date_idx`` backs the status+date
    filter); scoped like ``monthly_control`` so the report can never
    show days outside the requested client/dog filter.
    """
    queryset = Walk.objects.filter(
        status=Walk.STATUS_COMPLETED,
        date__gte=month_start,
        date__lte=month_end,
    ).order_by('date')
    if client is not None:
        queryset = queryset.filter(dog__client=client)
    if dog is not None:
        queryset = queryset.filter(dog=dog)

    dates_by_dog = {}
    for dog_id, walk_date in queryset.values_list('dog_id', 'date'):
        dates_by_dog.setdefault(dog_id, []).append(walk_date)
    return dates_by_dog


def group_monthly_control_by_client(rows):
    """Group monthly control rows by client with per-client subtotals.

    Rows must be sorted by client (``monthly_control`` already orders
    them by client name, dog name). Used by the monthly control view
    (RF-011) and by the dashboard (RF-010).
    """
    groups = []
    for client, group in groupby(rows, key=lambda row: row['client']):
        group_rows = list(group)
        totals = {
            counter: sum(row[counter] for row in group_rows)
            for counter in MONTHLY_COUNTERS
        }
        totals['progress'] = (
            round(100 * totals['completed'] / totals['contracted'])
            if totals['contracted']
            else 0
        )
        groups.append({'client': client, 'rows': group_rows, 'totals': totals})
    return groups
