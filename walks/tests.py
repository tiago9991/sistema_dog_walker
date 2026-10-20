"""Walks tests (Sprint 7/8 — RF-005..RF-009, RF-012/RF-013): deterministic
generation, window rules, idempotency, unique constraint, command, state
machine, period views, filters and status actions."""

from datetime import date, timedelta
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clients.models import Client
from dogs.models import Dog
from scheduling.models import WalkSchedule
from walks.models import Walk
from walks.services import (
    GENERATION_HORIZON_DAYS,
    GENERATION_LOOKBACK_DAYS,
    generate_walks,
    resync_dog_walks,
    transition_walk,
)

# Fixed "today" so window math is deterministic (Wednesday).
TODAY = date(2026, 10, 21)


class WalkTestBase(TestCase):
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

    def login(self, user):
        self.client.force_login(user)


class GenerationTests(WalkTestBase):
    """Sprint 7 — deterministic, idempotent generation (RF-005)."""

    def _create_mon_wed_fri_schedule(self, **kwargs):
        defaults = dict(
            dog=self.dog_a,
            start_date=date(2026, 10, 1),
            monday=True,
            wednesday=True,
            friday=True,
        )
        defaults.update(kwargs)
        return WalkSchedule.objects.create(**defaults)

    def test_generates_matching_weekdays_within_window(self):
        self._create_mon_wed_fri_schedule()
        stats = generate_walks(today=TODAY)

        # Window: [2026-10-14, 2026-11-20]
        # Mondays: 19/10, 26/10, 02/11, 09/11, 16/11 → 5
        # Wednesdays: 14/10, 21/10, 28/10, 04/11, 11/11, 18/11 → 6
        # Fridays: 16/10, 23/10, 30/10, 06/11, 13/11, 20/11 → 6
        self.assertEqual(stats['created'], 17)
        walks = Walk.objects.filter(dog=self.dog_a)
        self.assertEqual(walks.count(), 17)
        self.assertTrue(walks.filter(date=date(2026, 10, 19)).exists())  # Monday
        self.assertFalse(walks.filter(date=date(2026, 10, 20)).exists())  # Tuesday
        # Nothing before the window (schedule starts 01/10, window starts 14/10).
        self.assertFalse(walks.filter(date__lt=date(2026, 10, 14)).exists())
        # Nothing after the window.
        self.assertFalse(walks.filter(date__gt=TODAY + timedelta(days=30)).exists())

    def test_respects_end_date(self):
        self._create_mon_wed_fri_schedule(end_date=date(2026, 10, 25))
        generate_walks(today=TODAY)
        # Only 14/10 (Wed), 16/10 (Fri), 19/10 (Mon), 21/10 (Wed), 23/10 (Fri).
        self.assertEqual(Walk.objects.filter(dog=self.dog_a).count(), 5)
        self.assertFalse(
            Walk.objects.filter(dog=self.dog_a, date__gt=date(2026, 10, 25)).exists()
        )

    def test_respects_start_date(self):
        self._create_mon_wed_fri_schedule(start_date=date(2026, 11, 1))
        generate_walks(today=TODAY)
        # November only: 02, 04, 06, 09, 11, 13, 16, 18, 20 → 9.
        self.assertEqual(Walk.objects.filter(dog=self.dog_a).count(), 9)
        self.assertFalse(
            Walk.objects.filter(dog=self.dog_a, date__lt=date(2026, 11, 1)).exists()
        )

    def test_skips_inactive_schedule_dog_and_client(self):
        client_c = Client.objects.create(name='Cliente C', is_active=False)
        dog_c = Dog.objects.create(client=client_c, name='Thor', is_active=False)
        WalkSchedule.objects.create(
            dog=dog_c, start_date=date(2026, 10, 1), monday=True
        )
        WalkSchedule.objects.create(
            dog=self.dog_b, start_date=date(2026, 10, 1), is_active=False, tuesday=True
        )
        stats = generate_walks(today=TODAY)
        self.assertEqual(stats['created'], 0)
        self.assertFalse(Walk.objects.exists())

    def test_idempotent_second_run_creates_nothing(self):
        self._create_mon_wed_fri_schedule()
        first = generate_walks(today=TODAY)
        second = generate_walks(today=TODAY)
        self.assertEqual(first['created'], 17)
        self.assertEqual(second['created'], 0)
        self.assertEqual(second['existing'], 17)
        self.assertEqual(Walk.objects.filter(dog=self.dog_a).count(), 17)

    def test_existing_walk_is_never_duplicated_or_overwritten(self):
        existing = Walk.objects.create(
            dog=self.dog_a, date=date(2026, 10, 21), status=Walk.STATUS_COMPLETED
        )
        self._create_mon_wed_fri_schedule()
        stats = generate_walks(today=TODAY)
        self.assertEqual(stats['created'], 16)
        self.assertEqual(stats['existing'], 1)
        existing.refresh_from_db()
        self.assertEqual(existing.status, Walk.STATUS_COMPLETED)

    def test_unique_constraint_blocks_duplicates(self):
        Walk.objects.create(dog=self.dog_a, date=date(2026, 10, 21))
        with self.assertRaises(IntegrityError), transaction.atomic():
            Walk.objects.create(dog=self.dog_a, date=date(2026, 10, 21))

    def test_custom_window_overrides(self):
        self._create_mon_wed_fri_schedule()
        stats = generate_walks(today=TODAY, lookback_days=0, horizon_days=0)
        # Only TODAY (Wednesday) itself.
        self.assertEqual(stats['created'], 1)
        self.assertTrue(
            Walk.objects.filter(dog=self.dog_a, date=TODAY).exists()
        )


class GenerationCommandTests(WalkTestBase):
    def test_command_generates_and_is_idempotent(self):
        WalkSchedule.objects.create(
            dog=self.dog_a,
            start_date=timezone.localdate() - timedelta(days=1),
            monday=True,
            tuesday=True,
            wednesday=True,
            thursday=True,
            friday=True,
            saturday=True,
            sunday=True,
        )
        stdout = StringIO()
        call_command('generate_walks', stdout=stdout)
        first_output = stdout.getvalue()
        self.assertIn('Geração concluída', first_output)
        first_count = Walk.objects.count()
        self.assertGreater(first_count, 0)

        stdout = StringIO()
        call_command('generate_walks', stdout=stdout)
        self.assertIn('0 passeio(s) criado(s)', stdout.getvalue())
        self.assertEqual(Walk.objects.count(), first_count)

    def test_command_reports_window_defaults(self):
        stdout = StringIO()
        call_command(
            'generate_walks', '--lookback', str(GENERATION_LOOKBACK_DAYS),
            '--horizon', str(GENERATION_HORIZON_DAYS), stdout=stdout,
        )
        self.assertIn('Geração concluída', stdout.getvalue())


class TimezoneTests(WalkTestBase):
    def test_current_timezone_is_sao_paulo(self):
        self.assertEqual(timezone.get_current_timezone_name(), 'America/Sao_Paulo')

    def test_localdate_matches_settings_timezone(self):
        self.assertEqual(str(timezone.localtime().tzinfo), 'America/Sao_Paulo')
        self.assertIsInstance(timezone.localdate(), date)


class TransitionServiceTests(WalkTestBase):
    def _walk(self, status=Walk.STATUS_SCHEDULED, notes=''):
        return Walk.objects.create(
            dog=self.dog_a, date=date(2026, 10, 21), status=status, notes=notes
        )

    def test_scheduled_to_completed_sets_timestamp(self):
        walk = self._walk()
        transition_walk(walk, Walk.STATUS_COMPLETED)
        walk.refresh_from_db()
        self.assertEqual(walk.status, Walk.STATUS_COMPLETED)
        self.assertIsNotNone(walk.status_changed_at)

    def test_cancel_with_observation_appends_to_notes(self):
        walk = self._walk(notes='Observação original.')
        transition_walk(
            walk, Walk.STATUS_CANCELLED, observation='Cliente viajou.'
        )
        walk.refresh_from_db()
        self.assertEqual(walk.status, Walk.STATUS_CANCELLED)
        self.assertIn('Observação original.', walk.notes)
        self.assertIn('Cancelado: Cliente viajou.', walk.notes)
        self.assertIn('[', walk.notes)  # timestamped entry

    def test_revert_returns_to_scheduled(self):
        walk = self._walk(status=Walk.STATUS_MISSED)
        transition_walk(walk, Walk.STATUS_SCHEDULED)
        walk.refresh_from_db()
        self.assertEqual(walk.status, Walk.STATUS_SCHEDULED)

    def test_invalid_transitions_raise(self):
        walk = self._walk(status=Walk.STATUS_COMPLETED)
        with self.assertRaises(ValidationError):
            transition_walk(walk, Walk.STATUS_CANCELLED)
        with self.assertRaises(ValidationError):
            transition_walk(walk, Walk.STATUS_COMPLETED)  # same status
        walk.refresh_from_db()
        self.assertEqual(walk.status, Walk.STATUS_COMPLETED)


class ResyncTests(WalkTestBase):
    def test_deactivated_schedule_leaves_only_past_walks(self):
        today = timezone.localdate()
        schedule = WalkSchedule.objects.create(
            dog=self.dog_a,
            start_date=today - timedelta(days=10),
            end_date=today + timedelta(days=10),
            monday=True, tuesday=True, wednesday=True, thursday=True,
            friday=True, saturday=True, sunday=True,
        )
        generate_walks(today=today)
        schedule.is_active = False
        schedule.save()
        resync_dog_walks(self.dog_a, today=today)
        self.assertFalse(
            Walk.objects.filter(dog=self.dog_a, date__gte=today).exists()
        )
        # Past walks are history — they stay.
        self.assertTrue(
            Walk.objects.filter(dog=self.dog_a, date__lt=today).exists()
        )


class WalkViewTests(WalkTestBase):
    """Sprint 8 — day/week/month/history lists + filters (RF-006/RF-012)."""

    def setUp(self):
        # dog_a: Mon/Wed/Fri; dog_b: Tuesday — deterministic fixed window.
        WalkSchedule.objects.create(
            dog=self.dog_a,
            start_date=date(2026, 10, 1),
            monday=True, wednesday=True, friday=True,
        )
        WalkSchedule.objects.create(
            dog=self.dog_b, start_date=date(2026, 10, 1), tuesday=True
        )
        generate_walks(today=TODAY)

    def test_day_view_shows_only_that_day(self):
        self.login(self.operator)
        response = self.client.get(reverse('walks:day'), {'date': '2026-10-19'})
        self.assertEqual(
            {walk.dog.name for walk in response.context['walks']}, {'Rex'}
        )

        response = self.client.get(reverse('walks:day'), {'date': '2026-10-20'})
        self.assertEqual(
            {walk.dog.name for walk in response.context['walks']}, {'Bidu'}
        )

    def test_day_view_defaults_to_today(self):
        self.login(self.operator)
        response = self.client.get(reverse('walks:day'))
        self.assertEqual(response.status_code, 200)

    def test_day_view_ignores_garbage_input(self):
        self.login(self.operator)
        response = self.client.get(reverse('walks:day'), {'date': 'banana'})
        self.assertEqual(response.status_code, 200)

    def test_week_view_covers_monday_to_sunday(self):
        self.login(self.operator)
        response = self.client.get(reverse('walks:week'), {'date': '2026-10-19'})
        self.assertEqual(response.status_code, 200)
        # Week 19–25/10: Rex (Mon 19, Wed 21, Fri 23) + Bidu (Tue 20).
        self.assertEqual(len(response.context['walks']), 4)

    def test_month_view_scopes_to_month(self):
        self.login(self.operator)
        response = self.client.get(reverse('walks:month'), {'month': '2026-10'})
        self.assertEqual(response.status_code, 200)
        # October window part — dog_a: 14,16,19,21,23,26,28,30 (Mon/Wed/Fri);
        # dog_b: 20,27 (Tue) → 10 walks.
        self.assertEqual(len(response.context['walks']), 10)

        response = self.client.get(reverse('walks:month'), {'month': '2026-11'})
        # November: dog_a 2,4,6,9,11,13,16,18,20 + dog_b 3,10,17 → 12.
        self.assertEqual(len(response.context['walks']), 12)

    def test_history_view_is_descending_and_filterable(self):
        self.login(self.operator)
        response = self.client.get(reverse('walks:history'), {'month': '2026-11'})
        self.assertEqual(response.status_code, 200)
        walks = list(response.context['walks'])
        self.assertGreater(len(walks), 1)
        self.assertGreaterEqual(walks[0].date, walks[-1].date)

        response = self.client.get(
            reverse('walks:history'), {'month': '2026-11', 'dog': self.dog_a.pk}
        )
        self.assertEqual(
            {walk.dog_id for walk in response.context['walks']},
            {self.dog_a.pk},
        )

    def test_client_and_status_filters(self):
        self.login(self.operator)
        # Complete one walk, then filter by status.
        walk = Walk.objects.get(dog=self.dog_a, date=date(2026, 10, 21))
        transition_walk(walk, Walk.STATUS_COMPLETED)

        response = self.client.get(
            reverse('walks:day'), {'date': '2026-10-21', 'status': 'completed'}
        )
        self.assertEqual(
            {(walk.dog.name, walk.status) for walk in response.context['walks']},
            {('Rex', Walk.STATUS_COMPLETED)},
        )

        response = self.client.get(
            reverse('walks:day'),
            {'date': '2026-10-21', 'status': 'scheduled'},
        )
        # Rex is completed; Bidu (Tuesdays only) has no walk on a Wednesday.
        self.assertEqual({walk.dog.name for walk in response.context['walks']}, set())

        response = self.client.get(
            reverse('walks:day'),
            {'date': '2026-10-20', 'status': 'scheduled'},
        )
        self.assertEqual(
            {walk.dog.name for walk in response.context['walks']}, {'Bidu'}
        )

        response = self.client.get(
            reverse('walks:day'), {'date': '2026-10-20', 'client': self.client_b.pk}
        )
        self.assertEqual(
            {walk.dog.name for walk in response.context['walks']}, {'Bidu'}
        )

    def test_dog_history_visible_on_dog_detail(self):
        self.login(self.reader)
        response = self.client.get(
            reverse('dogs:detail', kwargs={'client_pk': self.client_a.pk, 'pk': self.dog_a.pk})
        )
        self.assertContains(response, 'Histórico de passeios')
        self.assertContains(response, 'Rex')

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse('walks:day'))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('walks:day')}",
            fetch_redirect_response=False,
        )

    def test_user_without_permissions_gets_403(self):
        self.login(self.no_access)
        for url_name in ('walks:day', 'walks:week', 'walks:month', 'walks:history'):
            self.assertEqual(
                self.client.get(reverse(url_name)).status_code, 403, url_name
            )

    def test_reader_can_list_but_not_act(self):
        self.login(self.reader)
        self.assertEqual(self.client.get(reverse('walks:day')).status_code, 200)
        walk = Walk.objects.get(dog=self.dog_a, date=date(2026, 10, 21))
        self.assertEqual(
            self.client.post(
                reverse('walks:complete', kwargs={'pk': walk.pk})
            ).status_code,
            403,
        )


class WalkActionTests(WalkTestBase):
    def setUp(self):
        self.walk = Walk.objects.create(
            dog=self.dog_a, date=timezone.localdate()
        )
        self.login(self.operator)

    def test_complete_action(self):
        response = self.client.post(reverse('walks:complete', kwargs={'pk': self.walk.pk}))
        self.assertEqual(response.status_code, 302)
        self.walk.refresh_from_db()
        self.assertEqual(self.walk.status, Walk.STATUS_COMPLETED)
        self.assertIsNotNone(self.walk.status_changed_at)

    def test_complete_action_requires_post(self):
        self.assertEqual(
            self.client.get(reverse('walks:complete', kwargs={'pk': self.walk.pk})).status_code,
            405,
        )

    def test_cancel_action_with_observation_form(self):
        url = reverse('walks:cancel', kwargs={'pk': self.walk.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cancelar passeio')

        response = self.client.post(
            url, {'observation': 'Chuva forte.'}, follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.walk.refresh_from_db()
        self.assertEqual(self.walk.status, Walk.STATUS_CANCELLED)
        self.assertIn('Cancelado: Chuva forte.', self.walk.notes)

    def test_miss_action_with_observation_form(self):
        url = reverse('walks:miss', kwargs={'pk': self.walk.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Registrar passeio não realizado')

        response = self.client.post(url, {'observation': 'Cachorro doente.'})
        self.assertEqual(response.status_code, 302)
        self.walk.refresh_from_db()
        self.assertEqual(self.walk.status, Walk.STATUS_MISSED)
        self.assertIn('Não realizado: Cachorro doente.', self.walk.notes)

    def test_revert_action(self):
        self.client.post(reverse('walks:complete', kwargs={'pk': self.walk.pk}))
        response = self.client.post(reverse('walks:revert', kwargs={'pk': self.walk.pk}))
        self.assertEqual(response.status_code, 302)
        self.walk.refresh_from_db()
        self.assertEqual(self.walk.status, Walk.STATUS_SCHEDULED)

    def test_invalid_transition_is_rejected_in_backend(self):
        # Completed → cancelled is not in the state machine: URL/request
        # manipulation must not apply it (RF-001 criterion).
        self.client.post(reverse('walks:complete', kwargs={'pk': self.walk.pk}))
        self.client.post(reverse('walks:cancel', kwargs={'pk': self.walk.pk}), follow=True)
        self.walk.refresh_from_db()
        self.assertEqual(self.walk.status, Walk.STATUS_COMPLETED)

    def test_actions_without_permissions(self):
        self.login(self.no_access)
        self.assertEqual(
            self.client.post(
                reverse('walks:complete', kwargs={'pk': self.walk.pk})
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse('walks:cancel', kwargs={'pk': self.walk.pk})).status_code,
            403,
        )
