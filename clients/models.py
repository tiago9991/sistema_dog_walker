"""Client domain models (PRD sections 8.3, 9.1 and RF-002)."""

from django.db import models

from base.models import BaseModel


class Client(BaseModel):
    """Person who hires the dog walking service.

    Business fields resolved in Sprint 4 (PRD section 53, item 1) and
    registered in PRD section 9.1.
    """

    name = models.CharField('nome', max_length=150)
    phone = models.CharField('telefone', max_length=20, blank=True)
    email = models.EmailField('e-mail', blank=True)
    notes = models.TextField('observações', blank=True)
    # Soft deactivation: history must be preserved (PRD RF-002).
    is_active = models.BooleanField('ativo', default=True)
    deactivated_at = models.DateTimeField('desativado em', null=True, blank=True)

    class Meta:
        verbose_name = 'cliente'
        verbose_name_plural = 'clientes'
        ordering = ('name',)
        indexes = (
            models.Index(fields=('name',), name='client_name_idx'),
            models.Index(fields=('is_active',), name='client_is_active_idx'),
        )

    def __str__(self):
        return self.name
