"""Background task for the AI domain (PRD section 19 — Sprint 12).

``monthly_analysis_task`` runs one ``AIAnalysis`` (created at dispatch by
the interface) inside the Celery worker — heavy LLM processing never
blocks a request (PRD section 19: "processamentos de IA demorados devem
ser executados via Celery"). The task persists the result (or the
failure reason) on the record and notifies the requester on completion
(RNF-004) with a link to the analysis detail.
"""

import logging

from celery import shared_task
from django.urls import reverse

from ai.models import AIAnalysis
from ai.services import run_monthly_analysis
from notifications.models import Notification
from notifications.services import notify

logger = logging.getLogger(__name__)


@shared_task
def monthly_analysis_task(analysis_id):
    """Run an AI analysis in the background and persist its outcome."""
    analysis = (
        AIAnalysis.objects.select_related('client', 'requested_by')
        .filter(pk=analysis_id)
        .first()
    )
    if analysis is None:
        # e.g. deleted between dispatch and run — nothing to do.
        logger.warning('AI analysis %s vanished before running.', analysis_id)
        return

    try:
        result, input_summary = run_monthly_analysis(analysis)
    except Exception as exc:
        logger.exception('AI analysis %s failed', analysis_id)
        analysis.mark_failed(exc)
        if analysis.requested_by:
            notify(
                analysis.requested_by,
                level=Notification.LEVEL_ERROR,
                title='Falha na análise de IA',
                message=(
                    f'{analysis.get_kind_display()}: a execução falhou — '
                    'veja os detalhes na análise.'
                ),
                link=reverse('ai:detail', args=[analysis.pk]),
            )
    else:
        analysis.mark_completed(result, input_summary=input_summary)
        if analysis.requested_by:
            notify(
                analysis.requested_by,
                level=Notification.LEVEL_SUCCESS,
                title='Análise de IA concluída',
                message=(
                    f'{analysis.get_kind_display()} de '
                    f'{analysis.period_display().capitalize()} está pronto — '
                    'clique para ver o resultado.'
                ),
                link=reverse('ai:detail', args=[analysis.pk]),
            )

    return {'analysis_id': analysis.pk, 'status': analysis.status}
