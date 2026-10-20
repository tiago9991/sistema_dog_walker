"""Dog URLs — always nested under their client (see clients.urls)."""

from django.urls import path

from dogs import views

app_name = 'dogs'

urlpatterns = [
    path('new/', views.DogCreateView.as_view(), name='create'),
    path('<int:pk>/', views.DogDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.DogUpdateView.as_view(), name='update'),
    path('<int:pk>/deactivate/', views.dog_deactivate, name='deactivate'),
    path('<int:pk>/activate/', views.dog_activate, name='activate'),
]
