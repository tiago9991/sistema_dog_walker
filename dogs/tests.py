"""Dogs tests (Sprint 5 — RF-003): CRUD nested under the client, multiple
dogs per client, deactivation history, cross-scope isolation and
permissions."""

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from clients.models import Client
from dogs.models import Dog


class DogTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.operator = User.objects.create_user('operador', password='op-senha-123')
        cls.operator.groups.add(Group.objects.get(name='Operação'))
        cls.reader = User.objects.create_user('leitor', password='rd-senha-123')
        cls.reader.groups.add(Group.objects.get(name='Leitura'))
        cls.no_access = User.objects.create_user('sem-acesso', password='na-senha-123')

        cls.client_a = Client.objects.create(name='Cliente A')
        cls.client_b = Client.objects.create(name='Cliente B')
        cls.dog_a = Dog.objects.create(client=cls.client_a, name='Rex')

    def login(self, user):
        self.client.force_login(user)


class DogCRUDTests(DogTestBase):
    def test_create_within_client(self):
        self.login(self.operator)
        response = self.client.get(
            reverse('dogs:create', kwargs={'client_pk': self.client_a.pk})
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse('dogs:create', kwargs={'client_pk': self.client_a.pk}),
            {'name': 'Bidu', 'breed': 'Vira-lata', 'notes': ''},
        )
        dog = Dog.objects.get(name='Bidu')
        self.assertEqual(dog.client, self.client_a)
        self.assertRedirects(
            response,
            reverse('dogs:detail', kwargs={'client_pk': self.client_a.pk, 'pk': dog.pk}),
        )

    def test_edit_and_detail(self):
        self.login(self.operator)
        response = self.client.post(
            reverse('dogs:update', kwargs={'client_pk': self.client_a.pk, 'pk': self.dog_a.pk}),
            {'name': 'Rex', 'breed': 'Pastor Alemão', 'notes': 'Muito energético'},
        )
        self.assertRedirects(
            response,
            reverse('dogs:detail', kwargs={'client_pk': self.client_a.pk, 'pk': self.dog_a.pk}),
        )
        self.dog_a.refresh_from_db()
        self.assertEqual(self.dog_a.breed, 'Pastor Alemão')

        response = self.client.get(
            reverse('dogs:detail', kwargs={'client_pk': self.client_a.pk, 'pk': self.dog_a.pk})
        )
        self.assertContains(response, 'Rex')
        self.assertContains(response, 'Pastor Alemão')

    def test_create_with_monthly_walks_quota(self):
        """Monthly package by quantity (decision 26/10/2026 — PRD
        RF-011): optional field; empty falls back to the
        schedule-derived contract."""
        self.login(self.operator)
        response = self.client.post(
            reverse('dogs:create', kwargs={'client_pk': self.client_a.pk}),
            {'name': 'Thor', 'breed': '', 'monthly_walks_quota': 15, 'notes': ''},
        )
        dog = Dog.objects.get(name='Thor')
        self.assertEqual(dog.monthly_walks_quota, 15)

        detail = self.client.get(
            reverse('dogs:detail', kwargs={'client_pk': self.client_a.pk, 'pk': dog.pk})
        )
        self.assertContains(detail, 'Passeios contratados por mês')
        self.assertContains(detail, '15')

    def test_quota_zero_is_rejected(self):
        # 0 is meaningless as a package (empty = derived) — ≥1 only.
        self.login(self.operator)
        response = self.client.post(
            reverse('dogs:create', kwargs={'client_pk': self.client_a.pk}),
            {'name': 'Thor', 'breed': '', 'monthly_walks_quota': 0, 'notes': ''},
        )
        self.assertEqual(response.status_code, 200)  # re-renders with errors
        self.assertFalse(Dog.objects.filter(name='Thor').exists())

    def test_edit_clears_quota_back_to_derived(self):
        self.dog_a.monthly_walks_quota = 15
        self.dog_a.save()
        self.login(self.operator)
        response = self.client.post(
            reverse('dogs:update', kwargs={'client_pk': self.client_a.pk, 'pk': self.dog_a.pk}),
            {'name': 'Rex', 'breed': '', 'monthly_walks_quota': '', 'notes': ''},
        )
        self.assertRedirects(
            response,
            reverse('dogs:detail', kwargs={'client_pk': self.client_a.pk, 'pk': self.dog_a.pk}),
        )
        self.dog_a.refresh_from_db()
        self.assertIsNone(self.dog_a.monthly_walks_quota)

    def test_client_can_own_multiple_dogs(self):
        Dog.objects.create(client=self.client_a, name='Bidu')
        Dog.objects.create(client=self.client_a, name='Thor')
        self.login(self.operator)
        response = self.client.get(
            reverse('clients:detail', kwargs={'pk': self.client_a.pk})
        )
        for name in ('Rex', 'Bidu', 'Thor'):
            self.assertContains(response, name)
        self.assertEqual(self.client_a.dogs.count(), 3)

    def test_deactivate_preserves_history(self):
        self.login(self.operator)
        response = self.client.post(
            reverse(
                'dogs:deactivate',
                kwargs={'client_pk': self.client_a.pk, 'pk': self.dog_a.pk},
            )
        )
        self.assertRedirects(
            response,
            reverse('dogs:detail', kwargs={'client_pk': self.client_a.pk, 'pk': self.dog_a.pk}),
        )
        self.dog_a.refresh_from_db()
        self.assertFalse(self.dog_a.is_active)
        self.assertIsNotNone(self.dog_a.deactivated_at)

        # History stays available after deactivation (RF-003).
        response = self.client.get(
            reverse('dogs:detail', kwargs={'client_pk': self.client_a.pk, 'pk': self.dog_a.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Desativado')

    def test_reactivate(self):
        self.login(self.operator)
        self.client.post(
            reverse(
                'dogs:deactivate',
                kwargs={'client_pk': self.client_a.pk, 'pk': self.dog_a.pk},
            )
        )
        self.client.post(
            reverse(
                'dogs:activate',
                kwargs={'client_pk': self.client_a.pk, 'pk': self.dog_a.pk},
            )
        )
        self.dog_a.refresh_from_db()
        self.assertTrue(self.dog_a.is_active)
        self.assertIsNone(self.dog_a.deactivated_at)

    def test_deactivate_requires_post(self):
        self.login(self.operator)
        response = self.client.get(
            reverse(
                'dogs:deactivate',
                kwargs={'client_pk': self.client_a.pk, 'pk': self.dog_a.pk},
            )
        )
        self.assertEqual(response.status_code, 405)

    def test_cross_scope_access_by_id_returns_404(self):
        """RF-003: a dog of another client must not be reachable by ID."""
        self.login(self.operator)
        response = self.client.get(
            reverse(
                'dogs:detail',
                kwargs={'client_pk': self.client_b.pk, 'pk': self.dog_a.pk},
            )
        )
        self.assertEqual(response.status_code, 404)

        response = self.client.post(
            reverse(
                'dogs:deactivate',
                kwargs={'client_pk': self.client_b.pk, 'pk': self.dog_a.pk},
            )
        )
        self.assertEqual(response.status_code, 404)
        self.dog_a.refresh_from_db()
        self.assertTrue(self.dog_a.is_active)

    def test_cannot_add_dog_to_deactivated_client(self):
        self.client_b.is_active = False
        self.client_b.save()
        self.login(self.operator)
        response = self.client.post(
            reverse('dogs:create', kwargs={'client_pk': self.client_b.pk}),
            {'name': 'Cachorro Inválido', 'breed': '', 'notes': ''},
        )
        self.assertRedirects(
            response, reverse('clients:detail', kwargs={'pk': self.client_b.pk})
        )
        self.assertFalse(
            Dog.objects.filter(client=self.client_b).exists()
        )


class DogPermissionTests(DogTestBase):
    def test_user_without_permissions_gets_403_everywhere(self):
        self.login(self.no_access)
        detail_kwargs = {'client_pk': self.client_a.pk, 'pk': self.dog_a.pk}

        self.assertEqual(
            self.client.get(
                reverse('dogs:create', kwargs={'client_pk': self.client_a.pk})
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse('dogs:create', kwargs={'client_pk': self.client_a.pk}),
                {'name': 'X'},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse('dogs:detail', kwargs=detail_kwargs)).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse('dogs:update', kwargs=detail_kwargs)).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(reverse('dogs:deactivate', kwargs=detail_kwargs)).status_code,
            403,
        )

    def test_reader_can_view_but_not_write(self):
        self.login(self.reader)
        detail_kwargs = {'client_pk': self.client_a.pk, 'pk': self.dog_a.pk}

        self.assertEqual(
            self.client.get(reverse('dogs:detail', kwargs=detail_kwargs)).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse('dogs:create', kwargs={'client_pk': self.client_a.pk})
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(reverse('dogs:update', kwargs=detail_kwargs)).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(reverse('dogs:deactivate', kwargs=detail_kwargs)).status_code,
            403,
        )
