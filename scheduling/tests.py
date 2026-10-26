"""Scheduling tests (Sprint 6 — RF-004): CRUD, validations, resync on
change, inactive-entity guards, permissions and scope isolation."""

from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clients.models import Client
from dogs.models import Dog
from scheduling.models import WalkSchedule
from walks.models import Walk
from walks.services import resync_dog_walks


class ScheduleTestBase(TestCase):
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

    def schedule_data(self, **overrides):
        data = {
            'frequency': 'weekly',
            'monday': 'on',
            'wednesday': 'on',
            'friday': 'on',
            'tuesday': '',
            'thursday': '',
            'saturday': '',
            'sunday': '',
            'start_date': (timezone.localdate() - timedelta(days=1)).isoformat(),
            'end_date': '',
        }
        data.update(overrides)
        return data

    def create_url(self, dog=None, client=None):
        dog = dog or self.dog_a
        client = client or dog.client
        return reverse(
            'scheduling:create', kwargs={'client_pk': client.pk, 'dog_pk': dog.pk}
        )


class ScheduleValidationTests(ScheduleTestBase):
    def test_requires_at_least_one_weekday(self):
        self.login(self.operator)
        response = self.client.post(self.create_url(), self.schedule_data(
            monday='', wednesday='', friday='',
        ))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Selecione ao menos um dia da semana.')
        self.assertFalse(WalkSchedule.objects.exists())

    def test_rejects_end_date_before_start_date(self):
        self.login(self.operator)
        response = self.client.post(self.create_url(), self.schedule_data(
            start_date='2026-10-01', end_date='2026-09-01',
        ))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'não pode ser anterior ao início')
        self.assertFalse(WalkSchedule.objects.exists())

    def test_blocks_overlapping_active_schedules_for_same_dog(self):
        self.login(self.operator)
        self.client.post(self.create_url(), self.schedule_data(start_date='2026-10-01'))
        # Same weekday (monday) and overlapping period → blocked.
        response = self.client.post(self.create_url(), self.schedule_data(
            monday='on', wednesday='', friday='', start_date='2026-11-01',
        ))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Já existe uma programação ativa')
        self.assertEqual(WalkSchedule.objects.count(), 1)

    def test_allows_disjoint_weekdays_overlapping_period(self):
        self.login(self.operator)
        self.client.post(self.create_url(), self.schedule_data(start_date='2026-10-01'))
        # Tuesday/Thursday never collide with monday/wednesday/friday.
        response = self.client.post(self.create_url(), self.schedule_data(
            monday='', tuesday='on', thursday='on', wednesday='', friday='',
        ))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(WalkSchedule.objects.count(), 2)

    def test_model_full_clean_enforces_weekdays(self):
        schedule = WalkSchedule(
            dog=self.dog_a, start_date='2026-10-01', frequency='weekly'
        )
        with self.assertRaises(ValidationError):
            schedule.full_clean()

    def test_check_constraint_rejects_schedule_without_weekdays(self):
        with self.assertRaises(Exception):
            WalkSchedule.objects.create(dog=self.dog_a, start_date='2026-10-01')


class ScheduleCrudTests(ScheduleTestBase):
    def test_create_generates_walks(self):
        self.login(self.operator)
        response = self.client.post(self.create_url(), self.schedule_data())
        self.assertRedirects(
            response, reverse('clients:detail', kwargs={'pk': self.client_a.pk})
        )
        schedule = WalkSchedule.objects.get(dog=self.dog_a)
        self.assertTrue(schedule.is_active)
        # Resync generated future 'previsto' walks for the dog.
        self.assertTrue(
            Walk.objects.filter(dog=self.dog_a, date__gte=timezone.localdate()).exists()
        )

    def test_edit_resyncs_future_walks(self):
        self.login(self.operator)
        self.client.post(self.create_url(), self.schedule_data())  # mon/wed/fri
        schedule = WalkSchedule.objects.get(dog=self.dog_a)

        # All weekdays now.
        data = self.schedule_data(
            monday='on', tuesday='on', wednesday='on', thursday='on',
            friday='on', saturday='on', sunday='on',
        )
        url = reverse(
            'scheduling:update',
            kwargs={'client_pk': self.client_a.pk, 'dog_pk': self.dog_a.pk, 'pk': schedule.pk},
        )
        response = self.client.post(url, data)
        self.assertRedirects(
            response, reverse('clients:detail', kwargs={'pk': self.client_a.pk})
        )
        today = timezone.localdate()
        # Every future day has a walk now.
        walk_dates = set(
            Walk.objects.filter(dog=self.dog_a, date__gte=today).values_list('date', flat=True)
        )
        self.assertIn(today, walk_dates)
        self.assertIn(today + timedelta(days=1), walk_dates)
        self.assertIn(today + timedelta(days=2), walk_dates)

    def test_deactivate_removes_future_previstos_and_preserves_past(self):
        self.login(self.operator)
        # All weekdays since the window start (today - 7), so past walks
        # exist on any weekday the suite runs. The default mon/wed/fri +
        # start_date = yesterday only creates past walks on some weekdays
        # (flaky: failed whenever the last two days had no matching weekday).
        data = self.schedule_data(
            start_date=(timezone.localdate() - timedelta(days=7)).isoformat(),
            monday='on', tuesday='on', wednesday='on', thursday='on',
            friday='on', saturday='on', sunday='on',
        )
        self.client.post(self.create_url(), data)
        schedule = WalkSchedule.objects.get(dog=self.dog_a)
        today = timezone.localdate()
        past_count = Walk.objects.filter(
            dog=self.dog_a, date__lt=today, status=Walk.STATUS_SCHEDULED
        ).count()
        self.assertGreater(past_count, 0)  # lookback created past walks

        url = reverse(
            'scheduling:deactivate',
            kwargs={'client_pk': self.client_a.pk, 'dog_pk': self.dog_a.pk, 'pk': schedule.pk},
        )
        response = self.client.post(url)
        self.assertRedirects(
            response, reverse('clients:detail', kwargs={'pk': self.client_a.pk})
        )
        schedule.refresh_from_db()
        self.assertFalse(schedule.is_active)
        self.assertIsNotNone(schedule.deactivated_at)
        # Future previstos removed; past walks preserved (history).
        self.assertFalse(
            Walk.objects.filter(dog=self.dog_a, date__gte=today).exists()
        )
        self.assertEqual(
            Walk.objects.filter(
                dog=self.dog_a, date__lt=today, status=Walk.STATUS_SCHEDULED
            ).count(),
            past_count,
        )

    def test_activate_regenerates_walks(self):
        self.login(self.operator)
        self.client.post(self.create_url(), self.schedule_data())
        schedule = WalkSchedule.objects.get(dog=self.dog_a)
        url = reverse(
            'scheduling:activate',
            kwargs={'client_pk': self.client_a.pk, 'dog_pk': self.dog_a.pk, 'pk': schedule.pk},
        )
        # Deactivate then activate.
        self.client.post(
            reverse(
                'scheduling:deactivate',
                kwargs={'client_pk': self.client_a.pk, 'dog_pk': self.dog_a.pk, 'pk': schedule.pk},
            )
        )
        response = self.client.post(url)
        self.assertRedirects(
            response, reverse('clients:detail', kwargs={'pk': self.client_a.pk})
        )
        schedule.refresh_from_db()
        self.assertTrue(schedule.is_active)
        self.assertTrue(
            Walk.objects.filter(dog=self.dog_a, date__gte=timezone.localdate()).exists()
        )

    def test_create_blocked_for_deactivated_dog(self):
        self.dog_b.is_active = False
        self.dog_b.save()
        self.login(self.operator)
        response = self.client.post(self.create_url(dog=self.dog_b), self.schedule_data())
        self.assertRedirects(
            response, reverse('clients:detail', kwargs={'pk': self.client_b.pk})
        )
        self.assertFalse(WalkSchedule.objects.filter(dog=self.dog_b).exists())

    def test_create_blocked_for_deactivated_client(self):
        self.client_b.is_active = False
        self.client_b.save()
        self.login(self.operator)
        response = self.client.post(self.create_url(dog=self.dog_b), self.schedule_data())
        self.assertRedirects(
            response, reverse('clients:detail', kwargs={'pk': self.client_b.pk})
        )
        self.assertFalse(WalkSchedule.objects.filter(dog=self.dog_b).exists())


class SchedulePermissionTests(ScheduleTestBase):
    def test_anonymous_redirected_to_login(self):
        response = self.client.get(self.create_url())
        login_url = f"{reverse('login')}?next={self.create_url()}"
        self.assertRedirects(response, login_url, fetch_redirect_response=False)

    def test_user_without_permissions_gets_403(self):
        self.login(self.no_access)
        self.assertEqual(self.client.get(self.create_url()).status_code, 403)
        self.assertEqual(
            self.client.post(self.create_url(), self.schedule_data()).status_code, 403
        )

    def test_reader_cannot_create(self):
        self.login(self.reader)
        self.assertEqual(self.client.get(self.create_url()).status_code, 403)
        self.assertEqual(
            self.client.post(self.create_url(), self.schedule_data()).status_code, 403
        )

    def test_deactivate_requires_post(self):
        self.login(self.operator)
        self.client.post(self.create_url(), self.schedule_data())
        schedule = WalkSchedule.objects.get(dog=self.dog_a)
        url = reverse(
            'scheduling:deactivate',
            kwargs={'client_pk': self.client_a.pk, 'dog_pk': self.dog_a.pk, 'pk': schedule.pk},
        )
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_scope_isolation_by_id(self):
        self.login(self.operator)
        self.client.post(self.create_url(), self.schedule_data())
        schedule = WalkSchedule.objects.get(dog=self.dog_a)
        # Schedule of dog_a (client A) accessed under client B / dog B → 404.
        for name, method in (('update', 'get'), ('deactivate', 'post')):
            url = reverse(
                f'scheduling:{name}',
                kwargs={'client_pk': self.client_b.pk, 'dog_pk': self.dog_b.pk, 'pk': schedule.pk},
            )
            response = getattr(self.client, method)(url, data={} if method == 'post' else None)
            self.assertEqual(response.status_code, 404, name)


class ResyncServiceTests(ScheduleTestBase):
    def test_resync_preserves_non_scheduled_walks(self):
        today = timezone.localdate()
        schedule = WalkSchedule.objects.create(
            dog=self.dog_a,
            start_date=today - timedelta(days=10),
            end_date=today + timedelta(days=10),
            monday=True, tuesday=True, wednesday=True, thursday=True,
            friday=True, saturday=True, sunday=True,
        )
        # Fill the whole window (lookback 7 + horizon 30, capped by end_date).
        from walks.services import generate_walks
        generate_walks(today=today)
        total = Walk.objects.filter(dog=self.dog_a).count()
        self.assertGreaterEqual(total, 18)

        # A future completed walk and a past cancelled walk must survive.
        future_walk = Walk.objects.get(dog=self.dog_a, date=today + timedelta(days=1))
        future_walk.status = Walk.STATUS_COMPLETED
        future_walk.save()
        past_walk = Walk.objects.get(dog=self.dog_a, date=today - timedelta(days=1))
        past_walk.status = Walk.STATUS_CANCELLED
        past_walk.save()

        resync_dog_walks(self.dog_a, today=today)

        future_walk.refresh_from_db()
        past_walk.refresh_from_db()
        self.assertEqual(future_walk.status, Walk.STATUS_COMPLETED)
        self.assertEqual(past_walk.status, Walk.STATUS_CANCELLED)
        # 'previsto' walks were deleted and regenerated — plus the backfill:
        # the schedule starts 10 days back, so the resync window now reaches
        # its own start and creates the 3 days the default lookback (7) had
        # missed (decision 2026-10-26 — PRD section 53).
        self.assertEqual(
            Walk.objects.filter(dog=self.dog_a).count(), total + 3
        )
        # Today was regenerated as 'previsto'.
        self.assertEqual(
            Walk.objects.get(dog=self.dog_a, date=today).status,
            Walk.STATUS_SCHEDULED,
        )
        schedule.delete()  # cleanup: PROTECT would keep rows anyway (no-op)
