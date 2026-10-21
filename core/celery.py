"""Celery application (PRD sections 7 and 18 — Sprint 11).

Broker: RabbitMQ (``CELERY_BROKER_URL``); result backend/cache: Redis
(Django cache — ``REDIS_URL``). Standard Django integration layout:

- ``core.celery.app`` is created here and imported by ``core.__init__``
  so it is always loaded (including the management commands);
- tasks live in ``<app>.tasks`` modules (autodiscovered);
- configuration comes from ``django.conf:settings`` with the ``CELERY_``
  namespace (e.g. settings ``CELERY_BROKER_URL``).
"""

import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('core')

app.config_from_object('django.conf:settings', namespace='CELERY')

# Daily walk generation (PRD RF-005/section 18): every day at 03:00
# America/Sao_Paulo (CELERY_TIMEZONE), keeping the window ahead filled.
app.conf.beat_schedule = {
    'generate-walks-daily': {
        'task': 'walks.tasks.generate_walks_task',
        'schedule': crontab(hour=3, minute=0),
    },
}

app.autodiscover_tasks()
