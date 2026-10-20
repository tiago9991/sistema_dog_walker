"""Clients tests (Sprint 4 — RF-002): CRUD, search, deactivation,
permissions and data isolation."""

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from clients.models import Client


class ClientTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.operator = User.objects.create_user('operador', password='op-senha-123')
        cls.operator.groups.add(Group.objects.get(name='Operação'))
        cls.reader = User.objects.create_user('leitor', password='rd-senha-123')
        cls.reader.groups.add(Group.objects.get(name='Leitura'))
        cls.no_access = User.objects.create_user('sem-acesso', password='na-senha-123')

    def login(self, user):
        self.client.force_login(user)


class ClientCRUDTests(ClientTestBase):
    def test_create_edit_detail_list_and_search(self):
        self.login(self.operator)

        response = self.client.post(
            reverse('clients:create'),
            {
                'name': 'Marina Costa',
                'phone': '(11) 98888-7777',
                'email': 'marina@example.com',
                'notes': 'Cliente da zona sul',
            },
        )
        client_obj = Client.objects.get(name='Marina Costa')
        self.assertRedirects(
            response, reverse('clients:detail', kwargs={'pk': client_obj.pk})
        )
        self.assertIsNotNone(client_obj.created_at)
        self.assertIsNotNone(client_obj.updated_at)

        response = self.client.post(
            reverse('clients:update', kwargs={'pk': client_obj.pk}),
            {
                'name': 'Marina Costa Silva',
                'phone': '(11) 98888-7777',
                'email': 'marina@example.com',
                'notes': 'Cliente da zona sul',
            },
        )
        self.assertRedirects(
            response, reverse('clients:detail', kwargs={'pk': client_obj.pk})
        )
        client_obj.refresh_from_db()
        self.assertEqual(client_obj.name, 'Marina Costa Silva')

        response = self.client.get(
            reverse('clients:detail', kwargs={'pk': client_obj.pk})
        )
        self.assertContains(response, 'Marina Costa Silva')
        self.assertContains(response, 'marina@example.com')

        Client.objects.create(name='Outro Cliente')
        response = self.client.get(reverse('clients:list'))
        self.assertContains(response, 'Marina Costa Silva')
        self.assertContains(response, 'Outro Cliente')

        response = self.client.get(reverse('clients:list'), {'q': 'marina'})
        self.assertContains(response, 'Marina Costa Silva')
        self.assertNotContains(response, 'Outro Cliente')

    def test_deactivate_preserves_history_and_status_filters(self):
        self.login(self.operator)
        client_obj = Client.objects.create(name='Marina Costa')

        response = self.client.post(
            reverse('clients:deactivate', kwargs={'pk': client_obj.pk})
        )
        self.assertRedirects(
            response, reverse('clients:detail', kwargs={'pk': client_obj.pk})
        )
        client_obj.refresh_from_db()
        self.assertFalse(client_obj.is_active)
        self.assertIsNotNone(client_obj.deactivated_at)

        # Detail stays accessible: history preserved (RF-002).
        response = self.client.get(
            reverse('clients:detail', kwargs={'pk': client_obj.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Desativado')

        # Default list shows everyone (with badge); filters scope it.
        self.assertContains(self.client.get(reverse('clients:list')), 'Marina Costa')
        self.assertNotContains(
            self.client.get(reverse('clients:list'), {'status': 'active'}),
            'Marina Costa',
        )
        self.assertContains(
            self.client.get(reverse('clients:list'), {'status': 'inactive'}),
            'Marina Costa',
        )

    def test_reactivate(self):
        self.login(self.operator)
        client_obj = Client.objects.create(
            name='Marina Costa', is_active=False, deactivated_at='2026-01-01T10:00:00+00:00'
        )
        response = self.client.post(
            reverse('clients:activate', kwargs={'pk': client_obj.pk})
        )
        self.assertRedirects(
            response, reverse('clients:detail', kwargs={'pk': client_obj.pk})
        )
        client_obj.refresh_from_db()
        self.assertTrue(client_obj.is_active)
        self.assertIsNone(client_obj.deactivated_at)

    def test_deactivate_requires_post(self):
        self.login(self.operator)
        client_obj = Client.objects.create(name='Marina Costa')
        response = self.client.get(
            reverse('clients:deactivate', kwargs={'pk': client_obj.pk})
        )
        self.assertEqual(response.status_code, 405)

    def test_pagination(self):
        self.login(self.operator)
        for index in range(1, 26):
            Client.objects.create(name=f'Cliente {index:02d}')
        response = self.client.get(reverse('clients:list'), {'page': 2})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cliente 21')
        self.assertNotContains(response, 'Cliente 01')


class ClientPermissionTests(ClientTestBase):
    """RF-001: permissions are enforced in the backend, including by ID."""

    def test_user_without_permissions_gets_403_everywhere(self):
        self.login(self.no_access)
        client_obj = Client.objects.create(name='Marina Costa')

        self.assertEqual(self.client.get(reverse('clients:list')).status_code, 403)
        self.assertEqual(self.client.get(reverse('clients:create')).status_code, 403)
        self.assertEqual(
            self.client.post(reverse('clients:create'), {'name': 'X'}).status_code,
            403,
        )
        # Direct ID access does not bypass authorization.
        self.assertEqual(
            self.client.get(
                reverse('clients:detail', kwargs={'pk': client_obj.pk})
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                reverse('clients:update', kwargs={'pk': client_obj.pk})
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse('clients:deactivate', kwargs={'pk': client_obj.pk})
            ).status_code,
            403,
        )

    def test_reader_can_view_but_not_write(self):
        self.login(self.reader)
        client_obj = Client.objects.create(name='Marina Costa')

        self.assertEqual(self.client.get(reverse('clients:list')).status_code, 200)
        self.assertEqual(
            self.client.get(
                reverse('clients:detail', kwargs={'pk': client_obj.pk})
            ).status_code,
            200,
        )
        self.assertEqual(self.client.get(reverse('clients:create')).status_code, 403)
        self.assertEqual(
            self.client.post(reverse('clients:create'), {'name': 'X'}).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                reverse('clients:update', kwargs={'pk': client_obj.pk})
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse('clients:deactivate', kwargs={'pk': client_obj.pk})
            ).status_code,
            403,
        )
