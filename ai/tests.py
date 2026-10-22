"""AI tests (Sprint 12 — PRD section 19, RNF-004): model, service (the
LLM is always mocked — tests never call the OpenAI API), background
task with its completion notification, views and permissions."""

from datetime import date
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse

from ai.models import AIAnalysis
from ai.services import (
    NO_DATA_MESSAGE,
    NO_DATA_SUMMARY,
    run_monthly_analysis,
)
from ai.tasks import monthly_analysis_task
from clients.models import Client
from dogs.models import Dog
from notifications.models import Notification
from scheduling.models import WalkSchedule
from walks.models import Walk

ANALYSIS_MONTH = '2026-10'


def fake_chat_model(content='Análise de teste.'):
    """A stand-in for the LangChain chat model.

    A plain callable is wrapped as a RunnableLambda by the chain, so the
    service code path (``prompt | model``) is the real one — only the
    provider call is replaced.
    """

    def model(inputs):
        return SimpleNamespace(content=content)

    return model


class AITestBase(TestCase):
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

    def create_analysis(self, **kwargs):
        defaults = dict(
            kind=AIAnalysis.KIND_MONTHLY_SUMMARY,
            status=AIAnalysis.STATUS_RUNNING,
            month=ANALYSIS_MONTH,
            requested_by=self.operator,
        )
        defaults.update(kwargs)
        return AIAnalysis.objects.create(**defaults)

    def seed_month(self):
        """Deterministic October 2026 data (no generation-window math)."""
        WalkSchedule.objects.create(
            dog=self.dog_a,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 31),
            monday=True,
            wednesday=True,
        )
        Walk.objects.create(
            dog=self.dog_a, date=date(2026, 10, 5), status=Walk.STATUS_COMPLETED
        )
        # A cancelled walk with an observation (context for the model).
        cancelled = Walk(
            dog=self.dog_a, date=date(2026, 10, 7), status=Walk.STATUS_CANCELLED
        )
        cancelled.notes = '[21/10/2026 09:00] Cancelado: cliente viajou'
        cancelled.save()
        return cancelled


class AIAnalysisModelTests(AITestBase):
    def test_ordering_is_newest_first(self):
        first = self.create_analysis()
        second = self.create_analysis()
        analyses = list(AIAnalysis.objects.all())
        self.assertEqual(analyses[0], second)
        self.assertIn(first, analyses)

    def test_period_display_is_ptbr_month(self):
        analysis = self.create_analysis(month=ANALYSIS_MONTH)
        self.assertEqual(analysis.period_display(), 'Outubro 2026')

    def test_period_display_invalid_month_is_empty(self):
        for month in ('', 'banana', '2026-13'):
            analysis = self.create_analysis(month=month)
            self.assertEqual(analysis.period_display(), '', msg=month)

    def test_str_includes_kind_and_month(self):
        analysis = self.create_analysis()
        self.assertEqual(str(analysis), 'Resumo operacional mensal — 2026-10')

    def test_mark_completed_persists_result_and_snapshot(self):
        analysis = self.create_analysis()
        analysis.mark_completed('Resultado.', input_summary='dados')
        analysis.refresh_from_db()
        self.assertEqual(analysis.status, AIAnalysis.STATUS_COMPLETED)
        self.assertEqual(analysis.result, 'Resultado.')
        self.assertEqual(analysis.input_summary, 'dados')
        self.assertEqual(analysis.error, '')
        self.assertIsNotNone(analysis.completed_at)

    def test_mark_failed_persists_error(self):
        analysis = self.create_analysis()
        analysis.mark_failed('API fora do ar')
        analysis.refresh_from_db()
        self.assertEqual(analysis.status, AIAnalysis.STATUS_FAILED)
        self.assertIn('API fora do ar', analysis.error)
        self.assertIsNotNone(analysis.completed_at)


class MonthlyAnalysisServiceTests(AITestBase):
    """The chain runs against a fake model — no network, real code path."""

    def test_with_data_returns_result_and_snapshot(self):
        cancelled = self.seed_month()
        analysis = self.create_analysis(month=ANALYSIS_MONTH)

        with mock.patch(
            'ai.services.get_chat_model', return_value=fake_chat_model('Resumo ok.')
        ):
            result, snapshot = run_monthly_analysis(analysis)

        self.assertEqual(result, 'Resumo ok.')
        # Snapshot: counters per dog + totals + the month's observations.
        self.assertIn('Cliente A — Rex: contratados', snapshot)
        self.assertIn('realizados 1', snapshot)
        self.assertIn('cancelados 1', snapshot)
        self.assertIn('Totais do mês', snapshot)
        self.assertIn('Período: Outubro 2026', snapshot)
        self.assertIn('Escopo: todos os clientes', snapshot)
        self.assertIn(cancelled.notes.split(': ')[1], snapshot)

    def test_client_scope_lands_in_snapshot_and_llm_input(self):
        # Both clients have month data — the scope must exclude B.
        self.seed_month()
        WalkSchedule.objects.create(
            dog=self.dog_b,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 31),
            tuesday=True,
        )
        analysis = self.create_analysis(month=ANALYSIS_MONTH, client=self.client_a)
        seen = {}

        def model(inputs):
            seen['prompt'] = str(inputs)
            return SimpleNamespace(content='ok')

        with mock.patch('ai.services.get_chat_model', return_value=model):
            result, snapshot = run_monthly_analysis(analysis)

        self.assertEqual(result, 'ok')
        self.assertIn('Escopo: cliente Cliente A', snapshot)
        self.assertNotIn('Cliente B', snapshot)
        self.assertNotIn('Bidu', snapshot)
        # The prompt itself (what the model received) is scoped as well.
        self.assertIn('cliente Cliente A', seen['prompt'])
        self.assertNotIn('Cliente B', seen['prompt'])

    def test_no_data_short_circuits_without_llm_call(self):
        analysis = self.create_analysis(month='2030-01')

        def boom(inputs):
            raise AssertionError('LLM must not be called without data')

        with mock.patch('ai.services.get_chat_model', return_value=boom):
            result, snapshot = run_monthly_analysis(analysis)

        self.assertEqual(result, NO_DATA_MESSAGE)
        self.assertEqual(snapshot, NO_DATA_SUMMARY)

    def test_invalid_month_raises(self):
        analysis = self.create_analysis(month='banana')
        with self.assertRaises(ValueError):
            run_monthly_analysis(analysis)


class MonthlyAnalysisTaskTests(AITestBase):
    def test_task_completes_persists_and_notifies_requester(self):
        self.seed_month()
        analysis = self.create_analysis(month=ANALYSIS_MONTH)

        with mock.patch(
            'ai.services.get_chat_model', return_value=fake_chat_model('Resumo ok.')
        ):
            monthly_analysis_task(analysis.pk)

        analysis.refresh_from_db()
        self.assertEqual(analysis.status, AIAnalysis.STATUS_COMPLETED)
        self.assertEqual(analysis.result, 'Resumo ok.')
        self.assertIn('Cliente A', analysis.input_summary)
        self.assertIsNotNone(analysis.completed_at)

        notification = Notification.objects.get(recipient=self.operator)
        self.assertEqual(notification.level, Notification.LEVEL_SUCCESS)
        self.assertEqual(notification.title, 'Análise de IA concluída')
        # pt-br month label + link to the analysis detail.
        self.assertIn('Outubro 2026', notification.message)
        self.assertEqual(
            notification.link, reverse('ai:detail', args=[analysis.pk])
        )

    def test_task_failure_is_recorded_and_notified(self):
        self.seed_month()
        analysis = self.create_analysis(month=ANALYSIS_MONTH)

        with mock.patch(
            'ai.services.get_chat_model',
            side_effect=RuntimeError('api down'),
        ):
            monthly_analysis_task(analysis.pk)

        analysis.refresh_from_db()
        self.assertEqual(analysis.status, AIAnalysis.STATUS_FAILED)
        self.assertIn('api down', analysis.error)
        self.assertEqual(analysis.result, '')

        notification = Notification.objects.get(recipient=self.operator)
        self.assertEqual(notification.level, Notification.LEVEL_ERROR)
        self.assertEqual(notification.title, 'Falha na análise de IA')
        self.assertEqual(
            notification.link, reverse('ai:detail', args=[analysis.pk])
        )

    def test_task_without_requester_notifies_nobody(self):
        self.seed_month()
        analysis = self.create_analysis(requested_by=None)

        with mock.patch('ai.services.get_chat_model', return_value=fake_chat_model()):
            monthly_analysis_task(analysis.pk)

        analysis.refresh_from_db()
        self.assertEqual(analysis.status, AIAnalysis.STATUS_COMPLETED)
        self.assertFalse(Notification.objects.exists())

    def test_task_with_missing_analysis_is_noop(self):
        monthly_analysis_task(999_999)
        self.assertFalse(AIAnalysis.objects.exists())
        self.assertFalse(Notification.objects.exists())


@override_settings(OPENAI_API_KEY='sk-test')
class AIListViewTests(AITestBase):
    def test_list_requires_login(self):
        response = self.client.get(reverse('ai:list'))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('ai:list')}",
            fetch_redirect_response=False,
        )

    def test_list_requires_view_walk_permission(self):
        self.login(self.no_access)
        self.assertEqual(self.client.get(reverse('ai:list')).status_code, 403)

    def test_list_renders_history_and_form(self):
        self.seed_month()
        self.create_analysis(status=AIAnalysis.STATUS_COMPLETED, result='Bom mês.')
        self.login(self.operator)
        response = self.client.get(reverse('ai:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Resumo operacional mensal')
        self.assertContains(response, 'Outubro 2026')
        self.assertContains(response, 'Concluída')
        self.assertContains(response, 'data-async-task')
        self.assertContains(response, reverse('ai:request'))

    def test_list_prefills_month_and_client_from_query(self):
        self.create_analysis()
        self.login(self.operator)
        response = self.client.get(
            reverse('ai:list'), {'month': '2026-11', 'client': self.client_a.pk}
        )
        self.assertContains(response, 'value="2026-11"')
        self.assertContains(
            response, f'value="{self.client_a.pk}" selected'
        )

    def test_list_warns_when_not_configured(self):
        self.login(self.operator)
        with override_settings(OPENAI_API_KEY=''):
            response = self.client.get(reverse('ai:list'))
        self.assertContains(response, 'IA não configurada')
        self.assertNotContains(response, 'data-async-task')


class AIDetailViewTests(AITestBase):
    def test_detail_requires_login(self):
        analysis = self.create_analysis()
        url = reverse('ai:detail', args=[analysis.pk])
        response = self.client.get(url)
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={url}",
            fetch_redirect_response=False,
        )

    def test_detail_requires_view_walk_permission(self):
        analysis = self.create_analysis()
        self.login(self.no_access)
        response = self.client.get(reverse('ai:detail', args=[analysis.pk]))
        self.assertEqual(response.status_code, 403)

    def test_detail_shows_result_and_snapshot(self):
        self.seed_month()
        analysis = self.create_analysis(
            status=AIAnalysis.STATUS_COMPLETED,
            result='## Resumo\nBom mês.',
            input_summary='Período: outubro de 2026',
        )
        self.login(self.reader)  # read-only group can read analyses
        response = self.client.get(reverse('ai:detail', args=[analysis.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Bom mês.')
        self.assertContains(response, 'Dados considerados')
        self.assertContains(response, 'Período: outubro de 2026')
        self.assertContains(response, 'Concluída')

    def test_detail_running_shows_executing_message(self):
        analysis = self.create_analysis()
        self.login(self.operator)
        response = self.client.get(reverse('ai:detail', args=[analysis.pk]))
        self.assertContains(response, 'Análise em execução em segundo plano')

    def test_detail_failed_shows_error(self):
        analysis = self.create_analysis(
            status=AIAnalysis.STATUS_FAILED, error='api down'
        )
        self.login(self.operator)
        response = self.client.get(reverse('ai:detail', args=[analysis.pk]))
        self.assertContains(response, 'api down')


class AIRequestDispatchTests(AITestBase):
    """Sprint 12 — non-blocking dispatch (RNF-004 flow, as in Sprint 11).

    The task is patched, so these tests prove the REQUEST only creates
    the running record and dispatches: nothing runs synchronously and no
    notification is created during the request.
    """

    def setUp(self):
        super().setUp()
        patcher = mock.patch('ai.views.monthly_analysis_task')
        self.task = patcher.start()
        self.addCleanup(patcher.stop)

    @override_settings(OPENAI_API_KEY='sk-test')
    def test_ajax_dispatch_creates_running_record_and_delays(self):
        self.login(self.operator)
        response = self.client.post(
            reverse('ai:request'),
            {'month': ANALYSIS_MONTH, 'client': self.client_a.pk},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])
        self.assertIn('notificação', payload['detail'])

        analysis = AIAnalysis.objects.get()
        self.assertEqual(analysis.kind, AIAnalysis.KIND_MONTHLY_SUMMARY)
        self.assertEqual(analysis.status, AIAnalysis.STATUS_RUNNING)
        self.assertEqual(analysis.month, ANALYSIS_MONTH)
        self.assertEqual(analysis.client, self.client_a)
        self.assertEqual(analysis.requested_by, self.operator)
        self.task.delay.assert_called_once_with(analysis.pk)
        # RNF-004: the request itself completes no work and notifies
        # nobody — the worker does.
        self.assertEqual(analysis.result, '')
        self.assertFalse(Notification.objects.exists())

    @override_settings(OPENAI_API_KEY='sk-test')
    def test_non_ajax_dispatch_redirects_with_message(self):
        self.login(self.operator)
        response = self.client.post(
            reverse('ai:request'), {'month': ANALYSIS_MONTH}, follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.task.delay.assert_called_once()
        self.assertContains(response, 'iniciada em segundo plano')

    @override_settings(OPENAI_API_KEY='sk-test')
    def test_dispatch_defaults_month_to_current(self):
        self.login(self.operator)
        self.client.post(reverse('ai:request'), {'month': 'banana'})
        analysis = AIAnalysis.objects.get()
        self.assertRegex(analysis.month, r'^\d{4}-(0[1-9]|1[0-2])$')

    @override_settings(OPENAI_API_KEY='sk-test')
    def test_dispatch_ignores_unknown_client(self):
        self.login(self.operator)
        self.client.post(reverse('ai:request'), {'client': 999_999})
        self.assertIsNone(AIAnalysis.objects.get().client)

    @override_settings(OPENAI_API_KEY='sk-test')
    def test_dispatch_requires_post(self):
        self.login(self.operator)
        response = self.client.get(reverse('ai:request'))
        self.assertEqual(response.status_code, 405)
        self.task.delay.assert_not_called()

    @override_settings(OPENAI_API_KEY='sk-test')
    def test_dispatch_allowed_to_view_walk_holders(self):
        # Analyses are read-only derived data: 'Leitura' (view_walk) can
        # request them; a user without the permission cannot.
        self.login(self.reader)
        response = self.client.post(
            reverse('ai:request'), HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])

        self.login(self.no_access)
        self.assertEqual(
            self.client.post(reverse('ai:request')).status_code, 403
        )
        self.assertEqual(AIAnalysis.objects.count(), 1)

    @override_settings(OPENAI_API_KEY='sk-test')
    def test_anonymous_redirected_to_login(self):
        response = self.client.post(reverse('ai:request'))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('ai:request')}",
            fetch_redirect_response=False,
        )
        self.task.delay.assert_not_called()

    def test_not_configured_rejects_without_record(self):
        self.login(self.operator)
        with override_settings(OPENAI_API_KEY=''):
            response = self.client.post(
                reverse('ai:request'),
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()['ok'])
        self.assertFalse(AIAnalysis.objects.exists())
        self.task.delay.assert_not_called()

    @override_settings(OPENAI_API_KEY='sk-test')
    def test_broker_failure_marks_record_failed(self):
        self.task.delay.side_effect = OSError('broker unreachable')
        self.login(self.operator)
        response = self.client.post(
            reverse('ai:request'), HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()['ok'])
        analysis = AIAnalysis.objects.get()
        self.assertEqual(analysis.status, AIAnalysis.STATUS_FAILED)
        self.assertIn('Falha ao iniciar', analysis.error)


class ControlPageAITests(AITestBase):
    """The monthly control page links to the AI analysis (Sprint 12)."""

    def test_control_page_links_analysis_with_filters(self):
        self.login(self.operator)
        response = self.client.get(
            reverse('walks:control'), {'month': ANALYSIS_MONTH, 'client': self.client_a.pk}
        )
        self.assertContains(response, 'Analisar com IA')
        self.assertContains(
            response,
            f"{reverse('ai:list')}?month={ANALYSIS_MONTH}&client={self.client_a.pk}",
        )

    def test_sidebar_links_ai_for_authenticated_users(self):
        self.login(self.reader)
        response = self.client.get(reverse('home'))
        self.assertContains(response, reverse('ai:list'))
        self.assertContains(response, 'Análises de IA')
