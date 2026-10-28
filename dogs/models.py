"""Dog domain models (PRD sections 8.3, 9.1 and RF-003)."""

from django.core.validators import MinValueValidator
from django.db import models

from base.models import BaseModel
from clients.models import Client


class Dog(BaseModel):
    """Dog looked after by the service.

    Belongs to exactly one client, which may own many dogs
    (PRD section 9.1: ``Dog -> Client``).

    Business fields resolved in Sprint 5 (PRD section 53, item 2) and
    registered in PRD section 9.1.
    """

    # PROTECT: deleting a client must never silently destroy dog history
    # (PRD RF-002/RF-003 — historic data must be preserved).
    client = models.ForeignKey(
        Client,
        on_delete=models.PROTECT,
        related_name='dogs',
        verbose_name='cliente',
    )
    name = models.CharField('nome', max_length=150)
    breed = models.CharField('raça', max_length=100, blank=True)
    notes = models.TextField('observações', blank=True)
    # Monthly package by quantity (decision 2026-10-26 — PRD RF-011):
    # quantity contracts (e.g. 15 walks/month, flexible days) cannot be
    # expressed by weekday recurrence — 3 fixed days/week yields 13-15+
    # dates depending on the month. Empty = contract derived from the
    # dog's active schedules (current behavior).
    monthly_walks_quota = models.PositiveSmallIntegerField(
        'passeios contratados por mês',
        null=True,
        blank=True,
        validators=(MinValueValidator(1),),
        help_text=(
            'Pacote mensal por quantidade (ex.: 15/mês, dias flexíveis). '
            'Vazio = contratados derivados das programações.'
        ),
    )
    # Soft deactivation: history must be preserved (PRD RF-003).
    is_active = models.BooleanField('ativo', default=True)
    deactivated_at = models.DateTimeField('desativado em', null=True, blank=True)

    class Meta:
        verbose_name = 'cachorro'
        verbose_name_plural = 'cachorros'
        ordering = ('name',)
        indexes = (
            models.Index(fields=('name',), name='dog_name_idx'),
            # The client FK is auto-indexed by Django.
        )

    def __str__(self):
        return self.name
