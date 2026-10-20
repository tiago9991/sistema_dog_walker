"""Scheduling URLs — always nested under their dog (included from core.urls)."""

from django.urls import path

from scheduling import views

app_name = 'scheduling'

urlpatterns = [
    path('new/', views.ScheduleCreateView.as_view(), name='create'),
    path('<int:pk>/edit/', views.ScheduleUpdateView.as_view(), name='update'),
    path('<int:pk>/deactivate/', views.schedule_deactivate, name='deactivate'),
    path('<int:pk>/activate/', views.schedule_activate, name='activate'),
]
