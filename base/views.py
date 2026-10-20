"""Shared views."""

from django.http import JsonResponse


def health(request):
    """Liveness endpoint (PRD section 16).

    Requirements: HTTP 200, no authentication, no database access,
    minimal processing.
    """
    return JsonResponse({"status": "ok"})
