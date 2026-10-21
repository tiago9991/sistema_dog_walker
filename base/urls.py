"""Shared/root URLs: authentication and health (PRD sections 4, 16).

The application home (``/``) is the dashboard (``dashboard.urls``,
included in ``core.urls``); domain apps are included from ``core.urls``.
"""

from django.contrib.auth import views as auth_views
from django.urls import path

from base import views
from base.forms import LoginForm

urlpatterns = [
    path(
        'login/',
        auth_views.LoginView.as_view(
            template_name='base/login.html',
            authentication_form=LoginForm,
            redirect_authenticated_user=True,
        ),
        name='login',
    ),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    # PRD section 16: HTTP 200, no auth, no DB access.
    path('health/', views.health, name='health'),
]
