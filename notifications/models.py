"""Notifications domain models (PRD sections 8.3, 9.1 and RNF-004).

Model resolved in Sprint 11 (PRD section 53, item 13): **in-app**
notifications, personal to each user (no e-mail/push in the MVP), created
by background tasks to report task completion (RNF-004), surfaced in the
interface through the header bell (dropdown + unread badge), toasts and
the notifications page.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from base.models import BaseModel


class Notification(BaseModel):
    """An in-app notification for one user (PRD section 9.1)."""

    LEVEL_INFO = 'info'
    LEVEL_SUCCESS = 'success'
    LEVEL_WARNING = 'warning'
    LEVEL_ERROR = 'error'
    LEVEL_CHOICES = (
        (LEVEL_INFO, 'Informação'),
        (LEVEL_SUCCESS, 'Sucesso'),
        (LEVEL_WARNING, 'Atenção'),
        (LEVEL_ERROR, 'Erro'),
    )

    # Personal data: notifications are dropped with their user (the
    # history-preservation rule applies to business data, not to a
    # user's own inbox).
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='destinatário',
    )
    level = models.CharField(
        'nível',
        max_length=20,
        choices=LEVEL_CHOICES,
        default=LEVEL_INFO,
    )
    title = models.CharField('título', max_length=150)
    message = models.TextField('mensagem', blank=True)
    # Internal path (created by tasks, never user input), e.g. "/walks/dia/".
    link = models.CharField(
        'link',
        max_length=200,
        blank=True,
        help_text='Caminho interno opcional para detalhes (ex.: /walks/dia/).',
    )
    is_read = models.BooleanField('lida', default=False)
    read_at = models.DateTimeField('lida em', null=True, blank=True)

    class Meta:
        verbose_name = 'notificação'
        verbose_name_plural = 'notificações'
        ordering = ('-created_at',)
        indexes = (
            models.Index(
                fields=('recipient', '-created_at'),
                name='notif_recipient_created_idx',
            ),
            models.Index(
                fields=('recipient', 'is_read'),
                name='notif_recipient_read_idx',
            ),
        )

    def __str__(self):
        return f'{self.recipient} — {self.title}'

    def mark_read(self):
        """Idempotently mark as read (sets ``read_at`` once)."""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=('is_read', 'read_at', 'updated_at'))
        return self
