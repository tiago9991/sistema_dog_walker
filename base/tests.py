"""Shared/auth tests (Sprint 3 — RF-001, PRD sections 4 and 16)."""

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse


class HealthViewTests(TestCase):
    """PRD section 16: HTTP 200, no auth, no DB access."""

    def test_health_is_public_and_returns_ok(self):
        response = self.client.get(reverse('health'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})


class LoginViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='marina', password='senha-bem-secreta'
        )

    def test_login_page_renders_for_anonymous(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'base/login.html')

    def test_login_page_redirects_authenticated_users(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 302)

    def test_valid_login_creates_session_and_redirects(self):
        response = self.client.post(
            reverse('login'), {'username': 'marina', 'password': 'senha-bem-secreta'}
        )
        self.assertRedirects(response, reverse('home'), target_status_code=302)
        self.assertIn('_auth_user_id', self.client.session)

    def test_invalid_login_shows_error_and_no_session(self):
        response = self.client.post(
            reverse('login'), {'username': 'marina', 'password': 'errada'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Usuário ou senha inválidos.')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_logout_is_post_only_and_ends_session(self):
        self.client.force_login(self.user)
        self.assertIn(self.client.get(reverse('logout')).status_code, (405,))

        response = self.client.post(reverse('logout'))
        self.assertRedirects(response, reverse('login'), target_status_code=200)
        self.assertNotIn('_auth_user_id', self.client.session)


class RouteProtectionTests(TestCase):
    """RF-001: unauthenticated users cannot access protected areas."""

    def test_protected_route_redirects_anonymous_to_login(self):
        response = self.client.get(reverse('clients:list'))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('clients:list')}",
            fetch_redirect_response=False,
        )

    def test_home_redirects_to_clients_list(self):
        User.objects.create_user(username='marina', password='senha-bem-secreta')
        self.client.login(username='marina', password='senha-bem-secreta')
        response = self.client.get(reverse('home'), follow=True)
        # Followed to the clients list (403 only if the user has no perms).
        self.assertNotEqual(response.status_code, 302)


class AuthorizationGroupsTests(TestCase):
    """Sprint 3: groups created by the data migration (base.0001_groups)."""

    def test_groups_exist_with_expected_permissions(self):
        operacao = Group.objects.get(name='Operação')
        leitura = Group.objects.get(name='Leitura')

        operacao_codenames = set(
            operacao.permissions.values_list('codename', flat=True)
        )
        self.assertEqual(
            operacao_codenames,
            {
                'view_client',
                'add_client',
                'change_client',
                'view_dog',
                'add_dog',
                'change_dog',
            },
        )

        leitura_codenames = set(
            leitura.permissions.values_list('codename', flat=True)
        )
        self.assertEqual(leitura_codenames, {'view_client', 'view_dog'})

        # delete_* is never granted: history must be preserved (PRD RF-002/003)
        self.assertNotIn('delete_client', operacao_codenames)
        self.assertNotIn('delete_dog', operacao_codenames)
