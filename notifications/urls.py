"""Notification URLs (PRD RNF-004 — Sprint 11)."""

from django.urls import path

from notifications import views

app_name = 'notifications'

urlpatterns = [
    path('', views.NotificationListView.as_view(), name='list'),
    path('poll/', views.notifications_poll, name='poll'),
    path('marcar-lidas/', views.notifications_mark_all_read, name='mark_all_read'),
    path('<int:pk>/ler/', views.notification_mark_read, name='mark_read'),
]
