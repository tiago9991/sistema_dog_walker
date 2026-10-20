"""Walk generation and status transition services.

Implements PRD RF-005 (deterministic, idempotent generation),
RF-006 (state machine) and RF-007/RF-008 (transitions with observations).

Rules registered in the PRD (section 53, items 9 and 10, resolved):

- generation window: ``[today - 7 days, today + 30 days]`` (defaults,
  overridable per run); the lookback covers generation runs that did not
  happen (e.g. the machine was off) without creating walks older than the
  schedule itself;
- changing a schedule (create/edit/deactivate/activate) resynchronizes the
  dog's walks: future ``previsto`` walks are deleted and regenerated from
  the dog's active schedules; walks with any other status are preserved
  (history is never destroyed).
"""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from scheduling.models import WalkSchedule

from walks.models import Walk

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


def active_schedules(dog=None):
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
    """Reapply the dog's active schedules to its future ``previsto`` walks.

    Deletes the dog's future ``previsto`` walks and regenerates them from
    the dog's active schedules. Walks with any other status are preserved
    (history is never destroyed — PRD RF-007/RF-009).
    """
    today = today or timezone.localdate()
    with transaction.atomic():
        Walk.objects.filter(
            dog=dog, date__gte=today, status=Walk.STATUS_SCHEDULED
        ).delete()
        return generate_walks(today=today, dog=dog)


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
