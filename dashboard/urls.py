"""Dashboard URLs (PRD RF-010 — Sprint 10).

The dashboard is the application home (``/``, name ``home`` — kept
un-namespaced so every existing ``reverse('home')`` and
``LOGIN_REDIRECT_URL`` keeps working).
"""

from django.urls import path

from dashboard import views

urlpatterns = [
    path('', views.DashboardView.as_view(), name='home'),
]
