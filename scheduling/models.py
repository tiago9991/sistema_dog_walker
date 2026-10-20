"""Scheduling domain models (PRD sections 8.3, 9.1 and RF-004).

Recurrence model (Sprint 6 — PRD section 53, item 8, resolved): weekly
recurrence given by the selected weekdays, applied within an inclusive
period ``[start_date, end_date?]``; ``end_date`` empty means open-ended.
"""

from datetime import date

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from base.models import BaseModel
from dogs.models import Dog


class WalkSchedule(BaseModel):
    """Recurring walking plan for one dog (PRD section 9.1)."""

    WEEKDAY_FIELDS = (
        'monday',
        'tuesday',
        'wednesday',
        'thursday',
        'friday',
        'saturday',
        'sunday',
    )
    WEEKDAY_LABELS = {
        'monday': 'Seg',
        'tuesday': 'Ter',
        'wednesday': 'Qua',
        'thursday': 'Qui',
        'friday': 'Sex',
        'saturday': 'Sáb',
        'sunday': 'Dom',
    }

    FREQUENCY_WEEKLY = 'weekly'
    FREQUENCY_CHOICES = ((FREQUENCY_WEEKLY, 'Semanal'),)

    # PROTECT: deleting a dog must never silently destroy schedule history.
    dog = models.ForeignKey(
        Dog,
        on_delete=models.PROTECT,
        related_name='schedules',
        verbose_name='cachorro',
    )
    frequency = models.CharField(
        'frequência',
        max_length=20,
        choices=FREQUENCY_CHOICES,
        default=FREQUENCY_WEEKLY,
    )
    monday = models.BooleanField('segunda-feira', default=False)
    tuesday = models.BooleanField('terça-feira', default=False)
    wednesday = models.BooleanField('quarta-feira', default=False)
    thursday = models.BooleanField('quinta-feira', default=False)
    friday = models.BooleanField('sexta-feira', default=False)
    saturday = models.BooleanField('sábado', default=False)
    sunday = models.BooleanField('domingo', default=False)
    start_date = models.DateField('início do período')
    end_date = models.DateField(
        'fim do período', null=True, blank=True, help_text='Vazio = sem data final.'
    )
    # Soft deactivation, consistent with Client/Dog.
    is_active = models.BooleanField('ativo', default=True)
    deactivated_at = models.DateTimeField('desativado em', null=True, blank=True)

    class Meta:
        verbose_name = 'programação'
        verbose_name_plural = 'programações'
        ordering = ('-start_date', 'dog__name')
        indexes = (
            models.Index(fields=('dog',), name='schedule_dog_idx'),
            models.Index(fields=('is_active',), name='schedule_is_active_idx'),
        )
        constraints = (
            models.CheckConstraint(
                condition=(
                    models.Q(monday=True)
                    | models.Q(tuesday=True)
                    | models.Q(wednesday=True)
                    | models.Q(thursday=True)
                    | models.Q(friday=True)
                    | models.Q(saturday=True)
                    | models.Q(sunday=True)
                ),
                name='schedule_at_least_one_weekday',
            ),
        )

    def __str__(self):
        return f'{self.dog} — {self.weekday_summary}'

    @property
    def weekday_summary(self):
        """Short weekday list, e.g. ``Seg, Qua, Sex``."""
        return (
            ', '.join(
                self.WEEKDAY_LABELS[field]
                for field in self.WEEKDAY_FIELDS
                if getattr(self, field)
            )
            or '—'
        )

    def selected_weekday_indexes(self):
        """Weekday numbers (Monday=0 ... Sunday=6) enabled by this schedule."""
        return [
            index
            for index, field in enumerate(self.WEEKDAY_FIELDS)
            if getattr(self, field)
        ]

    def period_overlaps(self, other):
        self_end = self.end_date or date.max
        other_end = other.end_date or date.max
        return max(self.start_date, other.start_date) <= min(self_end, other_end)

    def shares_weekday(self, other):
        return any(
            getattr(self, field) and getattr(other, field)
            for field in self.WEEKDAY_FIELDS
        )

    def clean(self):
        super().clean()
        errors = {}

        if not any(getattr(self, field) for field in self.WEEKDAY_FIELDS):
            errors.setdefault('__all__', []).append(
                'Selecione ao menos um dia da semana.'
            )

        if self.start_date and self.end_date and self.end_date < self.start_date:
            errors.setdefault('end_date', []).append(
                'O fim do período não pode ser anterior ao início.'
            )

        # Two active schedules for the same dog must not generate walks for
        # the same date (the (dog, date) unique constraint would otherwise
        # silently pick only the first one — better to block it here).
        if self.dog_id:
            queryset = WalkSchedule.objects.filter(
                dog_id=self.dog_id, is_active=True
            ).exclude(pk=self.pk)
            for other in queryset:
                if self.period_overlaps(other) and self.shares_weekday(other):
                    errors.setdefault('__all__', []).append(
                        'Já existe uma programação ativa para este cachorro '
                        'que cobre estes dias da semana no mesmo período.'
                    )
                    break

        if errors:
            raise ValidationError(errors)
