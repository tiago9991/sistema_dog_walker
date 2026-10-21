"""Core project package.

Imports the Celery app (PRD section 18) so it is always loaded —
including from management commands and the production server.
"""

from core.celery import app as celery_app

__all__ = ('celery_app',)
