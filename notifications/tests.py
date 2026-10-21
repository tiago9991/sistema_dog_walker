"""Notifications tests (Sprint 11 — RNF-004): model, ownership scope,
mark-as-read actions and the poll endpoint used by the interface."""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from notifications.models import Notification
from notifications.services import notify


class NotificationTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user('alice', password='al-senha-123')
        cls.bob = User.objects.create_user('bob', password='bo-senha-123')

    def create(self, user, **kwargs):
        defaults = {
            'title': 'Tarefa concluída',
            'message': 'Geração de passeios concluída.',
            'level': Notification.LEVEL_SUCCESS,
            'link': '/walks/dia/',
        }
        defaults.update(kwargs)
        return notify(user, **defaults)

    def login(self, user):
        self.client.force_login(user)


class NotificationModelTests(NotificationTestBase):
    def test_mark_read_sets_read_at_once(self):
        notification = self.create(self.alice)
        self.assertFalse(notification.is_read)
        self.assertIsNone(notification.read_at)

        notification.mark_read()
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)
        self.assertIsNotNone(notification.read_at)

        read_at = notification.read_at
        notification.mark_read()  # idempotent
        notification.refresh_from_db()
        self.assertEqual(notification.read_at, read_at)

    def test_ordering_is_newest_first(self):
        first = self.create(self.alice, title='Primeira')
        second = self.create(self.alice, title='Segunda')
        notifications = list(Notification.objects.all())
        self.assertEqual(notifications[0], second)
        self.assertIn(first, notifications)

    def test_notify_creates_with_defaults(self):
        notification = notify(self.alice, title='Algo aconteceu')
        self.assertEqual(notification.level, Notification.LEVEL_INFO)
        self.assertEqual(notification.message, '')
        self.assertFalse(notification.is_read)


class NotificationScopeTests(NotificationTestBase):
    """Notifications are personal: only the recipient sees/acts on them."""

    def setUp(self):
        self.alice_notification = self.create(self.alice, title='Da Alice')
        self.bob_notification = self.create(self.bob, title='Do Bob')

    def test_list_shows_only_own_notifications(self):
        self.login(self.alice)
        response = self.client.get(reverse('notifications:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Da Alice')
        self.assertNotContains(response, 'Do Bob')

    def test_mark_read_on_foreign_notification_is_404(self):
        self.login(self.alice)
        response = self.client.post(
            reverse(
                'notifications:mark_read', kwargs={'pk': self.bob_notification.pk}
            )
        )
        self.assertEqual(response.status_code, 404)
        self.bob_notification.refresh_from_db()
        self.assertFalse(self.bob_notification.is_read)

    def test_mark_all_read_only_touches_own(self):
        self.login(self.alice)
        response = self.client.post(reverse('notifications:mark_all_read'))
        self.assertEqual(response.status_code, 302)
        self.alice_notification.refresh_from_db()
        self.bob_notification.refresh_from_db()
        self.assertTrue(self.alice_notification.is_read)
        self.assertFalse(self.bob_notification.is_read)

    def test_mark_read_requires_post(self):
        self.login(self.alice)
        response = self.client.get(
            reverse(
                'notifications:mark_read',
                kwargs={'pk': self.alice_notification.pk},
            )
        )
        self.assertEqual(response.status_code, 405)

    def test_external_next_is_rejected(self):
        # Open-redirect guard: a foreign ``next`` falls back to the list.
        self.login(self.alice)
        response = self.client.post(
            reverse('notifications:mark_all_read'),
            {'next': 'https://evil.example.com/'},
        )
        self.assertRedirects(response, reverse('notifications:list'))

    def test_anonymous_cannot_access_anything(self):
        for method, url in (
            ('get', reverse('notifications:list')),
            ('post', reverse('notifications:mark_all_read')),
            ('get', reverse('notifications:poll')),
        ):
            response = getattr(self.client, method)(url)
            self.assertRedirects(
                response,
                f"{reverse('login')}?next={url}",
                fetch_redirect_response=False,
                msg_prefix=url,
            )


class NotificationPollTests(NotificationTestBase):
    """The JSON endpoint polled by static/js/scsi.js (RNF-004)."""

    def test_first_poll_reports_state_without_new(self):
        notification = self.create(self.alice)
        self.login(self.alice)
        response = self.client.get(reverse('notifications:poll'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['unread'], 1)
        self.assertEqual(data['latest_id'], notification.pk)
        self.assertEqual(data['new'], [])

    def test_poll_after_returns_only_new_unread(self):
        old = self.create(self.alice, title='Antiga')
        self.login(self.alice)
        state = self.client.get(reverse('notifications:poll')).json()
        self.assertEqual(state['latest_id'], old.pk)

        fresh = self.create(self.alice, title='Nova')
        old.mark_read()

        response = self.client.get(
            reverse('notifications:poll'), {'after': state['latest_id']}
        )
        data = response.json()
        # Only the new unread one is reported (old, now read, is not).
        self.assertEqual([item['id'] for item in data['new']], [fresh.pk])
        self.assertEqual(data['unread'], 1)
        self.assertEqual(data['latest_id'], fresh.pk)
        item = data['new'][0]
        self.assertEqual(item['title'], 'Nova')
        self.assertEqual(item['level'], Notification.LEVEL_SUCCESS)
        self.assertEqual(item['link'], '/walks/dia/')
        self.assertIn('/', item['created_at'])  # formatted pt-br datetime

    def test_poll_never_leaks_other_users(self):
        self.create(self.bob, title='Do Bob')
        self.login(self.alice)
        data = self.client.get(
            reverse('notifications:poll'), {'after': 0}
        ).json()
        self.assertEqual(data['new'], [])
        self.assertEqual(data['unread'], 0)
        self.assertEqual(data['latest_id'], 0)

    def test_invalid_after_behaves_like_first_poll(self):
        self.create(self.alice)
        self.login(self.alice)
        data = self.client.get(
            reverse('notifications:poll'), {'after': 'banana'}
        ).json()
        self.assertEqual(data['new'], [])
        self.assertEqual(data['unread'], 1)


class NotificationHeaderBellTests(NotificationTestBase):
    """The header bell (base.html) consumes the context processor."""

    def test_header_bell_renders_unread_state(self):
        from django.contrib.auth.models import Group

        self.alice.groups.add(Group.objects.get(name='Leitura'))
        self.create(self.alice, title='Geração concluída')
        self.login(self.alice)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        # Badge + recent item + link to the full page.
        self.assertContains(response, 'data-notifications-badge')
        self.assertContains(response, 'Geração concluída')
        self.assertContains(response, 'Ver todas as notificações')
        self.assertContains(response, 'Marcar todas como lidas')

    def test_header_bell_without_notifications(self):
        from django.contrib.auth.models import Group

        self.alice.groups.add(Group.objects.get(name='Leitura'))
        self.login(self.alice)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nenhuma notificação.')
