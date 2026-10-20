"""Walk URLs (PRD RF-006/RF-008/RF-009/RF-012)."""

from django.urls import path
from django.views.generic import RedirectView

from walks import views

app_name = 'walks'

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='day'), name='index'),
    path('dia/', views.WalkDayListView.as_view(), name='day'),
    path('semana/', views.WalkWeekListView.as_view(), name='week'),
    path('mes/', views.WalkMonthListView.as_view(), name='month'),
    path('historico/', views.WalkHistoryListView.as_view(), name='history'),
    path('<int:pk>/realizado/', views.walk_complete, name='complete'),
    path('<int:pk>/cancelar/', views.walk_cancel, name='cancel'),
    path('<int:pk>/nao-realizado/', views.walk_miss, name='miss'),
    path('<int:pk>/reverter/', views.walk_revert, name='revert'),
]
