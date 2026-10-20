"""Walks domain models (PRD sections 8.3, 9.1 and RF-005/RF-006).

One walk per dog per date (Sprint 7 — PRD section 53, item 3, resolved):
the dog walking service visits each dog at most once a day, which is
enforced by the ``(dog, date)`` unique constraint and also protects the
generation against duplicates.
"""

from django.db import models

from base.models import BaseModel
from dogs.models import Dog


class Walk(BaseModel):
    """A planned/completed/cancelled walk (PRD section 9.1)."""

    STATUS_SCHEDULED = 'scheduled'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_MISSED = 'missed'

    STATUS_CHOICES = (
        (STATUS_SCHEDULED, 'Previsto'),
        (STATUS_COMPLETED, 'Realizado'),
        (STATUS_CANCELLED, 'Cancelado'),
        (STATUS_MISSED, 'Não realizado'),
    )

    # PROTECT: walk history must never be silently destroyed.
    dog = models.ForeignKey(
        Dog,
        on_delete=models.PROTECT,
        related_name='walks',
        verbose_name='cachorro',
    )
    date = models.DateField('data')
    status = models.CharField(
        'status', max_length=20, choices=STATUS_CHOICES, default=STATUS_SCHEDULED
    )
    notes = models.TextField('observações', blank=True)
    status_changed_at = models.DateTimeField('status alterado em', null=True, blank=True)

    class Meta:
        verbose_name = 'passeio'
        verbose_name_plural = 'passeios'
        ordering = ('date', 'dog__name')
        indexes = (
            models.Index(fields=('date',), name='walk_date_idx'),
            models.Index(fields=('status', 'date'), name='walk_status_date_idx'),
        )
        constraints = (
            models.UniqueConstraint(
                fields=('dog', 'date'),
                name='walk_dog_date_uniq',
            ),
        )

    def __str__(self):
        return f'{self.dog} — {self.date:%d/%m/%Y}'

    def status_label(self):
        return self.get_status_display()
