"""AI views: analysis history, detail and background dispatch
(PRD section 19 — Sprint 12; RNF-004).

Analyses derive from walks data, so every view is gated by
``walks.view_walk`` (the same permission that guards the monthly control
they are computed from — RF-011). The dispatch view creates the record
(``running``) and hands it to the Celery worker: the request returns
immediately and the requester receives a notification when the analysis
completes (RNF-004 — same ``data-async-task`` flow as the walk
generation, Sprint 11).
"""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView

from ai.llm import ai_configured
from ai.models import AIAnalysis
from ai.tasks import monthly_analysis_task
from clients.models import Client
from walks.services import parse_month

logger = logging.getLogger(__name__)


def _valid_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _is_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


def _current_month():
    today = timezone.localdate()
    return today.year, today.month


class AIAnalysisListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """Analysis history + the request form (first use case)."""

    permission_required = 'walks.view_walk'
    context_object_name = 'analyses'
    paginate_by = 20
    template_name = 'ai/analysis_list.html'

    def get_queryset(self):
        return AIAnalysis.objects.select_related('client', 'requested_by')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        parsed = parse_month(self.request.GET.get('month')) or _current_month()
        context.update(
            {
                'ai_configured': ai_configured(),
                'clients': Client.objects.order_by('name'),
                'current_month': f'{parsed[0]:04d}-{parsed[1]:02d}',
                'current_client_id': _valid_int(
                    self.request.GET.get('client')
                ),
            }
        )
        return context


class AIAnalysisDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """One analysis: status/result and the data snapshot the model saw."""

    permission_required = 'walks.view_walk'
    context_object_name = 'analysis'
    template_name = 'ai/analysis_detail.html'

    def get_queryset(self):
        return AIAnalysis.objects.select_related('client', 'requested_by')


@require_POST
@login_required
@permission_required('walks.view_walk', raise_exception=True)
def analysis_request(request):
    """Dispatch a new monthly analysis (RNF-004 — Sprint 12).

    Creates the ``running`` record and returns immediately — the worker
    runs the LLM call in the background and notifies the requester
    (with ``CELERY_TASK_ALWAYS_EAGER`` and no broker the task runs
    synchronously; the interface feedback flow is the same).
    """
    if not ai_configured():
        detail = (
            'IA não configurada: defina OPENAI_API_KEY no ambiente para '
            'solicitar análises.'
        )
        if _is_ajax(request):
            return JsonResponse({'ok': False, 'error': detail}, status=503)
        messages.error(request, detail)
        return redirect('ai:list')

    parsed = parse_month(request.POST.get('month')) or _current_month()
    client = Client.objects.filter(
        pk=_valid_int(request.POST.get('client'))
    ).first()

    analysis = AIAnalysis.objects.create(
        kind=AIAnalysis.KIND_MONTHLY_SUMMARY,
        status=AIAnalysis.STATUS_RUNNING,
        month=f'{parsed[0]:04d}-{parsed[1]:02d}',
        client=client,
        requested_by=request.user,
    )

    try:
        monthly_analysis_task.delay(analysis.pk)
    except Exception:
        logger.exception('AI analysis dispatch failed')
        analysis.mark_failed('Falha ao iniciar a tarefa em segundo plano.')
        detail = 'Não foi possível iniciar a análise de IA.'
        if _is_ajax(request):
            return JsonResponse({'ok': False, 'error': detail}, status=503)
        messages.error(request, detail)
        return redirect('ai:list')

    detail = (
        'Análise iniciada em segundo plano. '
        'Você receberá uma notificação ao concluir.'
    )
    if _is_ajax(request):
        return JsonResponse({'ok': True, 'detail': detail})
    messages.success(request, detail)
    return redirect('ai:list')
