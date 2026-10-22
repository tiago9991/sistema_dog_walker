"""AI URLs (PRD section 19 — Sprint 12)."""

from django.urls import path

from ai import views

app_name = 'ai'

urlpatterns = [
    path('', views.AIAnalysisListView.as_view(), name='list'),
    path('solicitar/', views.analysis_request, name='request'),
    path('<int:pk>/', views.AIAnalysisDetailView.as_view(), name='detail'),
]
