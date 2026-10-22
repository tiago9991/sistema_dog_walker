"""Report URLs (PRD section 21 — Sprint 13)."""

from django.urls import path

from reports import views

app_name = 'reports'

urlpatterns = [
    path(
        'controle-mensal/',
        views.MonthlyControlPdfView.as_view(),
        name='monthly_control_pdf',
    ),
]
