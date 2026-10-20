"""Client URLs. Dog routes live under ``/clients/<client_pk>/dogs/`` and are
included from ``core.urls`` so the ``dogs`` namespace registers at the root
(Django nested namespaces would otherwise require ``clients:dogs:...``)."""

from django.urls import path

from clients import views

app_name = 'clients'

urlpatterns = [
    path('', views.ClientListView.as_view(), name='list'),
    path('new/', views.ClientCreateView.as_view(), name='create'),
    path('<int:pk>/', views.ClientDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.ClientUpdateView.as_view(), name='update'),
    path('<int:pk>/deactivate/', views.client_deactivate, name='deactivate'),
    path('<int:pk>/activate/', views.client_activate, name='activate'),
]
