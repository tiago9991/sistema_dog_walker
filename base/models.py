"""Shared models for the ``base`` app.

``BaseModel`` centralizes the audit timestamps required by the PRD
(section 9.1) for every business entity (Client, Dog, Walk, ...).
"""

from django.db import models


class BaseModel(models.Model):
    """Abstract model with ``created_at``/``updated_at`` timestamps.

    Business models must inherit from this class instead of declaring
    the audit fields themselves, so every domain entity carries the
    same technical fields.
    """

    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        abstract = True
