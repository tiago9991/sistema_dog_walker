"""AI domain models (PRD sections 8.3, 9.1 and 19 — Sprint 12).

``AIAnalysis`` is the definitive persistence for AI results (section
9.1 — defined when the first use case was implemented): one record per
analysis run, created at dispatch (``running``) and updated by the
Celery task with the result or the failure reason. The data snapshot
sent to the model is preserved (``input_summary``) for audit and
transparency — the analysis detail shows exactly what the model saw.
"""

from datetime import date

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.formats import date_format

from base.models import BaseModel


class AIAnalysis(BaseModel):
    """A persisted AI analysis run (PRD section 9.1 — Sprint 12)."""

    KIND_MONTHLY_SUMMARY = 'monthly_summary'
    KIND_CHOICES = ((KIND_MONTHLY_SUMMARY, 'Resumo operacional mensal'),)

    STATUS_RUNNING = 'running'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = (
        (STATUS_RUNNING, 'Em execução'),
        (STATUS_COMPLETED, 'Concluída'),
        (STATUS_FAILED, 'Falhou'),
    )

    kind = models.CharField('tipo', max_length=20, choices=KIND_CHOICES)
    status = models.CharField(
        'status',
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_RUNNING,
    )
    # Analysis period ('YYYY-MM') for month-scoped kinds.
    month = models.CharField('mês', max_length=7, blank=True)
    # Optional scope preserved with the record (reproduces the run).
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.PROTECT,
        related_name='ai_analyses',
        null=True,
        blank=True,
        verbose_name='cliente',
    )
    # Data snapshot sent to the model (audit/transparency).
    input_summary = models.TextField('dados considerados', blank=True)
    result = models.TextField('resultado', blank=True)
    error = models.TextField('erro', blank=True)
    # Business data: the analysis survives its requester (only the user
    # reference is lost) — history-preservation rule (PRD RF-009).
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='ai_analyses',
        null=True,
        blank=True,
        verbose_name='solicitada por',
    )
    completed_at = models.DateTimeField('concluída em', null=True, blank=True)

    class Meta:
        verbose_name = 'análise de IA'
        verbose_name_plural = 'análises de IA'
        ordering = ('-created_at',)
        indexes = (
            models.Index(
                fields=('kind', '-created_at'), name='ai_kind_created_idx'
            ),
            models.Index(
                fields=('status', '-created_at'), name='ai_status_created_idx'
            ),
        )

    def __str__(self):
        if self.month:
            return f'{self.get_kind_display()} — {self.month}'
        return (
            f'{self.get_kind_display()} — '
            f'{timezone.localtime(self.created_at):%d/%m/%Y}'
        )

    def period_display(self):
        """``'Outubro 2026'`` (Django pt-br 'F Y') for the month ('' otherwise)."""
        try:
            year, month = int(self.month[:4]), int(self.month[5:7])
            return date_format(date(year, month, 1), 'F Y')
        except (ValueError, TypeError):
            return ''

    def mark_completed(self, result, input_summary=''):
        """Persist a successful run (result + data snapshot)."""
        self.status = self.STATUS_COMPLETED
        self.result = result
        self.input_summary = input_summary
        self.error = ''
        self.completed_at = timezone.now()
        self.save(
            update_fields=(
                'status',
                'result',
                'input_summary',
                'error',
                'completed_at',
                'updated_at',
            )
        )

    def mark_failed(self, error):
        """Persist a failed run (readable failure reason)."""
        self.status = self.STATUS_FAILED
        self.error = str(error)[:2000]
        self.completed_at = timezone.now()
        self.save(
            update_fields=(
                'status',
                'error',
                'completed_at',
                'updated_at',
            )
        )
