"""Notification services (PRD RNF-004 — task completion feedback)."""

from notifications.models import Notification


def notify(user, *, title, message='', level=Notification.LEVEL_INFO, link=''):
    """Create an in-app notification for ``user``.

    Used by background tasks to report their completion (RNF-004: "conclusão
    deve gerar notificação").
    """
    return Notification.objects.create(
        recipient=user,
        level=level,
        title=title,
        message=message,
        link=link,
    )
