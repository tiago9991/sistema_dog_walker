"""Shared/root URL configuration for the project (core.urls includes the
domain apps under their prefixes)."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('base.urls')),
    path('clients/', include('clients.urls')),
    # Dog routes stay under their client's URL scope (RF-003), included at
    # the root so the ``dogs`` namespace is directly reversible.
    path('clients/<int:client_pk>/dogs/', include('dogs.urls')),
]
