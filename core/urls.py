"""Shared/root URL configuration for the project (core.urls includes the
domain apps under their prefixes)."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # Celery panel in the Django Admin (PRD section 18 — Sprint 11). Must
    # come before the admin catch-all paths.
    path('admin/dj-control-room-base/', include('dj_control_room_base.urls')),
    path('admin/dj-celery-panel/', include('dj_celery_panel.urls')),
    path('admin/', admin.site.urls),
    # Dashboard is the application home (RF-010, Sprint 10) — un-namespaced
    # so ``reverse('home')`` keeps resolving.
    path('', include('dashboard.urls')),
    path('', include('base.urls')),
    path('clients/', include('clients.urls')),
    # Dog routes stay under their client's URL scope (RF-003), included at
    # the root so the ``dogs`` namespace is directly reversible.
    path('clients/<int:client_pk>/dogs/', include('dogs.urls')),
    # Schedules stay under their dog's URL scope (RF-004), same pattern.
    path(
        'clients/<int:client_pk>/dogs/<int:dog_pk>/schedules/',
        include('scheduling.urls'),
    ),
    path('walks/', include('walks.urls')),
    path('notifications/', include('notifications.urls')),
    # IA (PRD section 19 — Sprint 12) and reports (PRD section 21 —
    # Sprint 13).
    path('ai/', include('ai.urls')),
    path('reports/', include('reports.urls')),
]
