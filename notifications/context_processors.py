"""Context processor: header bell data (unread count + recent items).

Runs on every authenticated page render (PRD RNF-004: notifications must
surface in the interface). Two indexed queries (``recipient, is_read`` and
``recipient, -created_at``) — bounded and small.
"""

from notifications.models import Notification


def notifications(request):
    if not request.user.is_authenticated:
        return {}
    queryset = Notification.objects.filter(recipient=request.user)
    return {
        'unread_notifications_count': queryset.filter(is_read=False).count(),
        'recent_notifications': list(queryset[:5]),
    }
