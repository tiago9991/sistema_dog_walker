"""Background tasks for the walks domain (PRD sections 18/19, RNF-004).

``generate_walks_task`` wraps ``walks.services.generate_walks`` (RF-005)
for background execution: dispatched from the interface (walk generation
button — the requester is notified on completion, RNF-004) and scheduled
daily by Celery Beat (03:00 America/Sao_Paulo — see ``core/celery.py``).
"""

from celery import shared_task
from django.contrib.auth.models import User
from django.urls import reverse

from notifications.models import Notification
from notifications.services import notify
from walks.services import generate_walks


@shared_task
def generate_walks_task(user_id=None):
    """Generate the planned walks (RF-005) in the background.

    When ``user_id`` is given (interface dispatch), the requester receives
    an in-app notification with the result summary when the task completes
    (RNF-004). Scheduled runs (Beat, no user) do not notify anyone — the
    summary goes to the worker logs only.
    """
    stats = generate_walks()

    if user_id:
        user = User.objects.filter(pk=user_id).first()
        if user:
            notify(
                user,
                level=Notification.LEVEL_SUCCESS,
                title='Geração de passeios concluída',
                message=(
                    f"{stats['schedules']} programação(ões) considerada(s), "
                    f"{stats['created']} passeio(s) criado(s) e "
                    f"{stats['existing']} já existente(s)."
                ),
                link=reverse('walks:day'),
            )
    return stats
