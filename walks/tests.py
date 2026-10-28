"""Walks tests (Sprint 7/8/11 — RF-005..RF-009, RF-011/RF-012/RF-013,
RNF-004): deterministic generation, window rules, idempotency, unique
constraint, command, state machine, period views, filters, status
actions, monthly control and the background generation task."""

from datetime import date, timedelta
from io import StringIO
from unittest import mock

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clients.models import Client
from dogs.models import Dog
from notifications.models import Notification
from scheduling.models import WalkSchedule
from walks.models import Walk
from walks.services import (
    GENERATION_HORIZON_DAYS,
    GENERATION_LOOKBACK_DAYS,
    generate_walks,
    month_bounds,
    monthly_control,
    resync_dog_walks,
    transition_walk,
)
from walks.tasks import generate_walks_task

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

    def test_resync_backfills_from_backdated_schedule_start(self):
        """A schedule registered after its own start still gets its past
        contracted walks (decision 2026-10-26 — PRD section 53): without
        the backfill, dates before the 7-day lookback could never receive
        an outcome (the Giovana case: day 08/10 unrecordable)."""
        # Monday, 16 days before TODAY; the default lookback (7) only
        # reaches 14/10 — 05/10 and 12/10 are outside the regular window.
        WalkSchedule.objects.create(
            dog=self.dog_a, start_date=date(2026, 10, 5), monday=True
        )
        generate_walks(today=TODAY)
        self.assertFalse(
            Walk.objects.filter(
                dog=self.dog_a, date__lt=date(2026, 10, 12)
            ).exists()
        )
        # Resync (any schedule change) extends the window to the
        # schedule's own start: both Mondays are created as 'previsto'.
        resync_dog_walks(self.dog_a, today=TODAY)
        self.assertEqual(
            {
                Walk.objects.get(dog=self.dog_a, date=date(2026, 10, 5)).status,
                Walk.objects.get(dog=self.dog_a, date=date(2026, 10, 12)).status,
            },
            {Walk.STATUS_SCHEDULED},
        )

    def test_resync_backfill_preserves_resolved_and_is_idempotent(self):
        WalkSchedule.objects.create(
            dog=self.dog_a, start_date=date(2026, 10, 5), monday=True
        )
        resync_dog_walks(self.dog_a, today=TODAY)
        past_walk = Walk.objects.get(dog=self.dog_a, date=date(2026, 10, 5))
        transition_walk(past_walk, Walk.STATUS_COMPLETED)

        # A later schedule change must not touch the resolved past walk
        # (history is never destroyed)...
        resync_dog_walks(self.dog_a, today=TODAY)
        past_walk.refresh_from_db()
        self.assertEqual(past_walk.status, Walk.STATUS_COMPLETED)
        # ...and the backfill never duplicates (idempotent — RF-005).
        self.assertEqual(
            Walk.objects.filter(dog=self.dog_a, date=date(2026, 10, 5)).count(),
            1,
        )

    def test_resync_with_future_start_creates_nothing_before_it(self):
        WalkSchedule.objects.create(
            dog=self.dog_a, start_date=date(2026, 11, 5), thursday=True
        )
        resync_dog_walks(self.dog_a, today=TODAY)
        # No walk before the schedule's own start (clamping holds).
        dates = list(
            Walk.objects.filter(dog=self.dog_a)
            .order_by('date')
            .values_list('date', flat=True)
        )
        self.assertEqual(dates[0], date(2026, 11, 5))


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


class MonthlyControlServiceTests(WalkTestBase):
    """Sprint 9 — RF-011 calculation rules, validated with fabricated data.

    dog_a: Mon/Wed/Fri since 2026-10-01; generation window [2026-10-14,
    2026-11-20] creates the October walks from 14/10 onwards.
    """

    OCTOBER = (2026, 10)
    # Contracted Mon/Wed/Fri dates in October 2026: Mon 5,12,19,26;
    # Wed 7,14,21,28; Fri 2,9,16,23,30.
    DOG_A_CONTRACTED_OCTOBER = 13
    # Walks generated inside the window (from 14/10): 14,16,19,21,23,26,28,30.
    DOG_A_WALKS_OCTOBER = 8

    def setUp(self):
        WalkSchedule.objects.create(
            dog=self.dog_a,
            start_date=date(2026, 10, 1),
            monday=True,
            wednesday=True,
            friday=True,
        )
        generate_walks(today=TODAY)

    def _rows(self, year, month, **filters):
        rows, totals = monthly_control(*month_bounds(year, month), **filters)
        return {row['dog'].pk: row for row in rows}, totals

    def test_counters_with_mixed_statuses(self):
        # Fabricated outcomes: 3 completed, 1 cancelled, 1 missed in October.
        for walk_date in (date(2026, 10, 14), date(2026, 10, 16), date(2026, 10, 19)):
            transition_walk(
                Walk.objects.get(dog=self.dog_a, date=walk_date),
                Walk.STATUS_COMPLETED,
            )
        transition_walk(
            Walk.objects.get(dog=self.dog_a, date=date(2026, 10, 21)),
            Walk.STATUS_CANCELLED,
        )
        transition_walk(
            Walk.objects.get(dog=self.dog_a, date=date(2026, 10, 23)),
            Walk.STATUS_MISSED,
        )

        rows, totals = self._rows(*self.OCTOBER)
        row = rows[self.dog_a.pk]
        self.assertEqual(row['contracted'], self.DOG_A_CONTRACTED_OCTOBER)
        self.assertEqual(row['scheduled'], 3)  # 26, 28, 30
        self.assertEqual(row['completed'], 3)
        self.assertEqual(row['cancelled'], 1)
        self.assertEqual(row['missed'], 1)
        # remaining = contracted - completed - cancelled - missed.
        self.assertEqual(row['remaining'], 13 - 3 - 1 - 1)
        self.assertEqual(row['progress'], 23)  # round(100*3/13)

        for counter, value in (
            ('contracted', 13),
            ('scheduled', 3),
            ('completed', 3),
            ('cancelled', 1),
            ('missed', 1),
            ('remaining', 8),
        ):
            self.assertEqual(totals[counter], value, counter)

    def test_contracted_is_independent_of_generation_window(self):
        # December 2026 is beyond the generation horizon: contracted dates
        # still count (from the schedules), no walks exist yet.
        rows, totals = self._rows(2026, 12)
        row = rows[self.dog_a.pk]
        self.assertEqual(row['contracted'], 13)  # Mon/Wed/Fri in December
        self.assertEqual(row['scheduled'], 0)
        self.assertEqual(row['completed'], 0)
        self.assertEqual(row['remaining'], 13)

    def test_end_date_limits_contracted(self):
        schedule = WalkSchedule.objects.get(dog=self.dog_a)
        schedule.end_date = date(2026, 10, 15)
        schedule.save()
        rows, _ = self._rows(*self.OCTOBER)
        # Mon/Wed/Fri until 15/10: Mon 5,12; Wed 7,14; Fri 2,9.
        self.assertEqual(rows[self.dog_a.pk]['contracted'], 6)

    def test_remaining_never_negative_when_contract_shrinks(self):
        # All October walks completed, then the schedule is deactivated:
        # the current contract is zero, remaining is clamped at 0.
        for walk in Walk.objects.filter(dog=self.dog_a, date__lte=date(2026, 10, 31)):
            transition_walk(walk, Walk.STATUS_COMPLETED)
        schedule = WalkSchedule.objects.get(dog=self.dog_a)
        schedule.is_active = False
        schedule.save()
        rows, _ = self._rows(*self.OCTOBER)
        row = rows[self.dog_a.pk]
        self.assertEqual(row['contracted'], 0)
        self.assertEqual(row['completed'], self.DOG_A_WALKS_OCTOBER)
        self.assertEqual(row['remaining'], 0)

    def test_inactive_dog_keeps_history_but_has_no_contract(self):
        schedule = WalkSchedule.objects.create(
            dog=self.dog_b, start_date=date(2026, 10, 1), tuesday=True
        )
        generate_walks(today=TODAY)  # dog_b: 20/10, 27/10 within the window
        schedule.dog.is_active = False
        schedule.dog.save()

        rows, _ = self._rows(*self.OCTOBER)
        row = rows[self.dog_b.pk]
        self.assertEqual(row['contracted'], 0)  # excluded from the contract
        self.assertEqual(row['scheduled'], 2)  # history stays visible
        self.assertEqual(row['remaining'], 0)

    def test_dogs_without_walks_or_contract_are_not_listed(self):
        rows, _ = self._rows(*self.OCTOBER)
        self.assertIn(self.dog_a.pk, rows)
        self.assertNotIn(self.dog_b.pk, rows)  # no schedule, no walks

    def test_quota_replaces_calendar_derivation(self):
        """Monthly package by quantity (decision 26/10/2026 — PRD
        RF-011): the quota is the month's contract. The weekday calendar
        would report 13 (Mon/Wed/Fri in October), misleading the
        client-facing counters for quantity packages (15/month)."""
        self.dog_a.monthly_walks_quota = 15
        self.dog_a.save()

        rows, totals = self._rows(*self.OCTOBER)
        row = rows[self.dog_a.pk]
        self.assertEqual(row['contracted'], 15)  # quota, not 13
        self.assertEqual(row['scheduled'], self.DOG_A_WALKS_OCTOBER)
        self.assertEqual(row['remaining'], 15)  # no outcomes yet
        self.assertEqual(row['progress'], 0)
        self.assertEqual(totals['contracted'], 15)

    def test_quota_dog_without_schedule_is_listed(self):
        # Pure package client: no schedule, walks added by hand — the
        # quota alone contracts the month and lists the dog.
        self.dog_b.monthly_walks_quota = 15
        self.dog_b.save()

        rows, _ = self._rows(*self.OCTOBER)
        row = rows[self.dog_b.pk]
        self.assertEqual(row['contracted'], 15)
        self.assertEqual(row['scheduled'], 0)
        self.assertEqual(row['remaining'], 15)

    def test_quota_consumes_counters_and_clamps_remaining(self):
        # 3 completed of a 2-walk package (extra walks to reach the
        # client's quantity): over-delivery clamps remaining at 0 and
        # progress reports above 100% — delivered beyond the package.
        self.dog_a.monthly_walks_quota = 2
        self.dog_a.save()
        for walk_date in (date(2026, 10, 14), date(2026, 10, 16), date(2026, 10, 19)):
            transition_walk(
                Walk.objects.get(dog=self.dog_a, date=walk_date),
                Walk.STATUS_COMPLETED,
            )

        rows, _ = self._rows(*self.OCTOBER)
        row = rows[self.dog_a.pk]
        self.assertEqual(row['completed'], 3)
        self.assertEqual(row['remaining'], 0)  # never negative
        self.assertEqual(row['progress'], 150)  # round(100*3/2)

    def test_quota_ignored_for_inactive_dog(self):
        # Same rule as the schedule-derived contract: inactive dogs keep
        # their history (walks) but have no contract.
        self.dog_a.monthly_walks_quota = 15
        self.dog_a.is_active = False
        self.dog_a.save()

        rows, _ = self._rows(*self.OCTOBER)
        row = rows[self.dog_a.pk]
        self.assertEqual(row['contracted'], 0)
        self.assertEqual(row['scheduled'], self.DOG_A_WALKS_OCTOBER)
        self.assertEqual(row['remaining'], 0)

    def test_client_and_dog_filters(self):
        WalkSchedule.objects.create(
            dog=self.dog_b, start_date=date(2026, 10, 1), tuesday=True
        )
        generate_walks(today=TODAY)

        rows, _ = self._rows(*self.OCTOBER, client=self.client_a)
        self.assertEqual(set(rows), {self.dog_a.pk})

        rows, _ = self._rows(*self.OCTOBER, dog=self.dog_b)
        self.assertEqual(set(rows), {self.dog_b.pk})
        # Contracted Tuesdays in October: 6, 13, 20, 27.
        self.assertEqual(rows[self.dog_b.pk]['contracted'], 4)

    def test_month_without_contract_or_walks_is_empty(self):
        # Open-ended schedules contract indefinitely, so an empty month
        # requires a period bound: beyond the end_date there is no contract
        # and no walks were ever generated for December.
        schedule = WalkSchedule.objects.get(dog=self.dog_a)
        schedule.end_date = date(2026, 10, 31)
        schedule.save()
        rows, totals = self._rows(2026, 12)
        self.assertEqual(rows, {})
        self.assertEqual(totals['contracted'], 0)
        self.assertEqual(totals['remaining'], 0)


class MonthlyControlViewTests(WalkTestBase):
    """Sprint 9 — RF-011 per-client/per-dog views, filters and access."""

    def setUp(self):
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

    def test_control_view_groups_by_client_with_totals(self):
        self.login(self.operator)
        response = self.client.get(reverse('walks:control'), {'month': '2026-10'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Controle mensal')

        groups = {g['client'].name: g for g in response.context['client_groups']}
        self.assertEqual(set(groups), {'Cliente A', 'Cliente B'})
        # Visão por cliente: per-client subtotals; visão por cachorro: rows.
        self.assertEqual(
            {row['dog'].name for row in groups['Cliente A']['rows']}, {'Rex'}
        )
        self.assertEqual(groups['Cliente A']['totals']['contracted'], 13)
        self.assertEqual(groups['Cliente B']['totals']['contracted'], 4)

        totals = response.context['totals']
        self.assertEqual(totals['contracted'], 17)
        self.assertEqual(totals['scheduled'], 10)  # 8 (Rex) + 2 (Bidu)

    def test_client_filter_scopes_to_one_client(self):
        self.login(self.operator)
        response = self.client.get(
            reverse('walks:control'), {'month': '2026-10', 'client': self.client_a.pk}
        )
        groups = response.context['client_groups']
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['client'], self.client_a)
        self.assertEqual(response.context['totals']['contracted'], 13)

    def test_dog_filter_scopes_to_one_dog(self):
        self.login(self.operator)
        response = self.client.get(
            reverse('walks:control'), {'month': '2026-10', 'dog': self.dog_b.pk}
        )
        groups = response.context['client_groups']
        self.assertEqual(len(groups), 1)
        self.assertEqual(
            {row['dog'].name for row in groups[0]['rows']}, {'Bidu'}
        )

    def test_invalid_month_falls_back_to_current_month(self):
        self.login(self.operator)
        response = self.client.get(reverse('walks:control'), {'month': 'banana'})
        self.assertEqual(response.status_code, 200)
        today = timezone.localdate()
        self.assertEqual(
            response.context['current_month'],
            f'{today.year:04d}-{today.month:02d}',
        )

    def test_month_navigation_urls_keep_filters(self):
        self.login(self.operator)
        response = self.client.get(
            reverse('walks:control'),
            {'month': '2026-10', 'client': self.client_a.pk},
        )
        self.assertIn('month=2026-09', response.context['nav']['prev'])
        self.assertIn(f'client={self.client_a.pk}', response.context['nav']['prev'])
        self.assertIn('month=2026-11', response.context['nav']['next'])

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse('walks:control'))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('walks:control')}",
            fetch_redirect_response=False,
        )

    def test_user_without_permissions_gets_403(self):
        self.login(self.no_access)
        self.assertEqual(self.client.get(reverse('walks:control')).status_code, 403)

    def test_reader_can_view_control(self):
        self.login(self.reader)
        response = self.client.get(reverse('walks:control'), {'month': '2026-10'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cliente A')


class GenerateTaskTests(WalkTestBase):
    """Sprint 11 — background generation task (RF-005 via Celery, RNF-004)."""

    def _schedule(self):
        return WalkSchedule.objects.create(
            dog=self.dog_a,
            start_date=date(2026, 10, 1),
            monday=True,
            wednesday=True,
            friday=True,
        )

    def test_task_generates_and_notifies_requester(self):
        self._schedule()
        stats = generate_walks_task(user_id=self.operator.pk)

        self.assertGreater(stats['created'], 0)
        notification = Notification.objects.get(recipient=self.operator)
        self.assertEqual(notification.level, Notification.LEVEL_SUCCESS)
        self.assertIn('Geração de passeios concluída', notification.title)
        self.assertEqual(notification.link, reverse('walks:day'))
        self.assertIn(f"{stats['created']} passeio(s) criado(s)", notification.message)
        self.assertFalse(notification.is_read)

    def test_task_without_user_creates_no_notification(self):
        # Scheduled runs (Beat) have no requester — no notification.
        self._schedule()
        stats = generate_walks_task()
        self.assertGreater(stats['created'], 0)
        self.assertFalse(Notification.objects.exists())

    def test_task_with_unknown_user_is_safe(self):
        generate_walks_task(user_id=999_999)
        self.assertFalse(Notification.objects.exists())

    def test_task_is_idempotent(self):
        self._schedule()
        first = generate_walks_task()
        second = generate_walks_task()
        self.assertGreater(first['created'], 0)
        self.assertEqual(second['created'], 0)


class WalkDispatchTests(WalkTestBase):
    """Sprint 11 — non-blocking dispatch of the generation task (RNF-004).

    The task is patched, so these tests prove the REQUEST only dispatches:
    nothing runs synchronously and the response returns immediately.
    """

    def setUp(self):
        super().setUp()
        patcher = mock.patch('walks.views.generate_walks_task')
        self.task = patcher.start()
        self.addCleanup(patcher.stop)

    def test_ajax_dispatch_only_calls_delay(self):
        self.login(self.operator)
        response = self.client.post(
            reverse('walks:generate'),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])
        self.assertIn('notificação', payload['detail'])
        self.task.delay.assert_called_once_with(user_id=self.operator.pk)
        # RNF-004: the request itself created no walks/notifications —
        # the worker does the work.
        self.assertFalse(Walk.objects.exists())
        self.assertFalse(Notification.objects.exists())

    def test_non_ajax_dispatch_redirects_with_message(self):
        self.login(self.operator)
        response = self.client.post(reverse('walks:generate'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.task.delay.assert_called_once_with(user_id=self.operator.pk)
        self.assertContains(response, 'iniciada em segundo plano')

    def test_dispatch_requires_post(self):
        self.login(self.operator)
        response = self.client.get(reverse('walks:generate'))
        self.assertEqual(response.status_code, 405)
        self.task.delay.assert_not_called()

    def test_dispatch_requires_add_walk_permission(self):
        self.login(self.reader)  # view-only group
        self.assertEqual(
            self.client.post(reverse('walks:generate')).status_code, 403
        )
        self.task.delay.assert_not_called()

        self.login(self.no_access)
        self.assertEqual(
            self.client.post(reverse('walks:generate')).status_code, 403
        )

    def test_anonymous_redirected_to_login(self):
        response = self.client.post(reverse('walks:generate'))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('walks:generate')}",
            fetch_redirect_response=False,
        )
        self.task.delay.assert_not_called()

    def test_broker_failure_is_reported_not_raised(self):
        self.task.delay.side_effect = OSError('broker unreachable')
        self.login(self.operator)
        response = self.client.post(
            reverse('walks:generate'),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()['ok'])
        # The interface stays usable — the error is just feedback.

    def test_generate_button_renders_for_operators_only(self):
        self.login(self.operator)
        response = self.client.get(reverse('walks:day'))
        self.assertContains(response, reverse('walks:generate'))
        self.assertContains(response, 'data-async-task')

        self.login(self.reader)  # view-only: no button
        response = self.client.get(reverse('walks:day'))
        self.assertNotContains(response, reverse('walks:generate'))
