"""Dashboard tests (Sprint 10 — RF-010): indicators, aggregates, filters,
permissions, and a query budget that locks out N+1 regressions."""

from datetime import date

from django.contrib.auth.models import Group, User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from clients.models import Client
from dogs.models import Dog
from scheduling.models import WalkSchedule
from walks.models import Walk
from walks.services import generate_walks, transition_walk

# Fixed "today" so the generation window is deterministic (Wednesday):
# [2026-10-14, 2026-11-20]. October indicators are therefore stable no
# matter when the suite runs (the dashboard's month filter is explicit).
TODAY = date(2026, 10, 21)


class DashboardTestBase(TestCase):
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
        cls.dog_b = Dog.objects.create(client=cls.client_b, name='Bidu')

    def setUp(self):
        # dog_a: Mon/Wed/Fri (13 contracted dates in October); dog_b: Tuesday
        # (4 in October). Window [14/10, 20/11] → 10 walks in October.
        WalkSchedule.objects.create(
            dog=self.dog_a,
            start_date=date(2026, 10, 1),
            monday=True,
            wednesday=True,
            friday=True,
        )
        WalkSchedule.objects.create(
            dog=self.dog_b, start_date=date(2026, 10, 1), tuesday=True
        )
        generate_walks(today=TODAY)

    def login(self, user):
        self.client.force_login(user)


class DashboardIndicatorTests(DashboardTestBase):
    def test_entity_and_month_indicators(self):
        self.login(self.reader)
        response = self.client.get(reverse('home'), {'month': '2026-10'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Clientes ativos')
        self.assertContains(response, 'Cachorros ativos')

        self.assertEqual(response.context['clients_active'], 2)
        self.assertEqual(response.context['clients_total'], 2)
        self.assertEqual(response.context['dogs_active'], 2)
        self.assertEqual(response.context['dogs_total'], 2)

        # Month indicators reuse the RF-011 counters (Sprint 9).
        month = response.context['month_totals']
        self.assertEqual(month['contracted'], 17)  # 13 (Rex) + 4 (Bidu)
        self.assertEqual(month['scheduled'], 10)  # 8 (Rex) + 2 (Bidu)
        self.assertEqual(month['completed'], 0)
        self.assertEqual(month['cancelled'], 0)
        self.assertEqual(month['missed'], 0)
        self.assertEqual(month['remaining'], 17)
        self.assertEqual(month['progress'], 0)

        groups = {
            group['client'].name: group
            for group in response.context['client_groups']
        }
        self.assertEqual(set(groups), {'Cliente A', 'Cliente B'})
        self.assertEqual(groups['Cliente A']['totals']['contracted'], 13)
        self.assertEqual(groups['Cliente B']['totals']['contracted'], 4)

    def test_today_indicators(self):
        # Deterministic on any run date: a walk is ensured on the real
        # today, then completed — only relative invariants are asserted.
        today_walk, _ = Walk.objects.get_or_create(
            dog=self.dog_a, date=timezone.localdate()
        )
        transition_walk(today_walk, Walk.STATUS_COMPLETED)

        self.login(self.reader)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

        stats = response.context['today_stats']
        self.assertGreaterEqual(stats['total'], 1)
        self.assertEqual(stats['completed'], 1)
        self.assertEqual(stats['scheduled'], stats['total'] - 1)
        self.assertEqual(response.context['today_remaining'], stats['scheduled'])
        # Visão de passeios: today's walks include dog_a's.
        self.assertIn(
            self.dog_a.pk, {walk.dog_id for walk in response.context['today_walks']}
        )
        self.assertContains(response, 'Passeios de hoje')

    def test_month_and_client_filters(self):
        self.login(self.reader)
        response = self.client.get(
            reverse('home'),
            {'month': '2026-10', 'client': self.client_a.pk},
        )
        self.assertEqual(response.context['current_client_id'], self.client_a.pk)
        groups = response.context['client_groups']
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['client'], self.client_a)
        self.assertEqual(response.context['month_totals']['contracted'], 13)
        # Today's table is scoped to the client as well.
        self.assertNotIn(
            self.dog_b.pk, {walk.dog_id for walk in response.context['today_walks']}
        )

    def test_invalid_month_falls_back_to_current_month(self):
        self.login(self.reader)
        response = self.client.get(reverse('home'), {'month': 'banana'})
        self.assertEqual(response.status_code, 200)
        today = timezone.localdate()
        self.assertEqual(
            response.context['current_month'],
            f'{today.year:04d}-{today.month:02d}',
        )


class DashboardPermissionTests(DashboardTestBase):
    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse('home'))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('home')}",
            fetch_redirect_response=False,
        )

    def test_user_without_permissions_gets_403(self):
        self.login(self.no_access)
        self.assertEqual(self.client.get(reverse('home')).status_code, 403)

    def test_reader_can_view_but_has_no_action_forms(self):
        self.login(self.reader)
        Walk.objects.get_or_create(dog=self.dog_a, date=timezone.localdate())
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse('walks:complete', kwargs={'pk': 1}))

    def test_operator_sees_complete_action_for_scheduled_walk(self):
        self.login(self.operator)
        today_walk, _ = Walk.objects.get_or_create(
            dog=self.dog_a, date=timezone.localdate()
        )
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse('walks:complete', kwargs={'pk': today_walk.pk}),
        )


class DashboardQueryBudgetTests(DashboardTestBase):
    def test_query_count_stays_within_budget_with_many_dogs(self):
        # Scale the data (12 extra dogs) so an N+1 pattern would blow the
        # budget: per-row queries would add ~12+ queries over the baseline.
        for index in range(12):
            dog = Dog.objects.create(
                client=self.client_a, name=f'Extra {index:02d}'
            )
            WalkSchedule.objects.create(
                dog=dog,
                start_date=date(2026, 10, 1),
                monday=True,
                wednesday=True,
                friday=True,
            )
        generate_walks(today=TODAY)

        self.login(self.reader)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse('home'), {'month': '2026-10'})
        self.assertEqual(response.status_code, 200)
        # Baseline is ~12 queries (aggregates only); 20 leaves headroom
        # while failing loudly on any per-row query (14 dogs → +14).
        self.assertLessEqual(
            len(queries),
            20,
            msg=f'{len(queries)} queries — N+1 regression?\n'
            + '\n'.join(query['sql'] for query in queries),
        )
