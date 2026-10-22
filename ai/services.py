"""AI services: the first use case — monthly operational summary
(PRD section 19 — Sprint 12; use case registered in PRD section 53).

``run_monthly_analysis`` feeds the LangChain chain (``MONTHLY_ANALYSIS_PROMPT
| model`` — built through the ``ai.llm`` abstraction) with the monthly
control counters (``walks.services.monthly_control`` — RF-011, reused)
plus the month's registered observations, and returns the analysis text
with its data snapshot.

Design decisions:

- months without data short-circuit to a deterministic message without
  calling the LLM (no hallucination surface, no wasted call);
- the prompt receives aggregated counters and bounded observations
  only — the LLM never receives direct database access (no tools);
- the input snapshot is returned alongside the result so the task can
  persist both (audit: the detail page shows exactly what the model saw).
"""

from datetime import date

from django.utils.formats import date_format

from walks.models import Walk
from walks.services import month_bounds, monthly_control, parse_month

from ai.llm import get_chat_model
from ai.prompts import MONTHLY_ANALYSIS_PROMPT

# Bounds of the observations sent to the model (prompt size + privacy).
MAX_OBSERVATION_WALKS = 40
MAX_OBSERVATION_CHARS = 150

NO_DATA_MESSAGE = (
    'Não há dados de passeios ou programações para o período solicitado. '
    'Cadastre programações ativas ou gere os passeios do mês para que a '
    'análise tenha dados a considerar.'
)
NO_DATA_SUMMARY = 'Nenhum passeio ou programação no período.'


def month_label(year, month):
    """``'Outubro 2026'`` — pt-br month name for ``(year, month)``."""
    return date_format(date(year, month, 1), 'F Y')


def _counters_text(rows, totals):
    """One line per dog with the RF-011 counters + a totals line."""
    lines = [
        '{client} — {dog}: contratados {contracted}, previstos {scheduled}, '
        'realizados {completed}, cancelados {cancelled}, não realizados '
        '{missed}, restantes {remaining} ({progress}% do contrato realizado)'
        .format(
            client=row['client'].name,
            dog=row['dog'].name,
            **{counter: row[counter] for counter in (
                'contracted', 'scheduled', 'completed', 'cancelled', 'missed',
                'remaining', 'progress',
            )},
        )
        for row in rows
    ]
    lines.append(
        'Totais do mês: contratados {contracted}, previstos {scheduled}, '
        'realizados {completed}, cancelados {cancelled}, não realizados '
        '{missed}, restantes {remaining} ({progress}% do contrato realizado)'
        .format(**totals)
    )
    return '\n'.join(lines)


def _observations_text(month_start, month_end, client=None):
    """The month's registered walk observations, bounded.

    Observations carry the reasons behind cancellations/misses
    (RF-008/RF-013) — valuable context for the analysis. Bounded to keep
    the prompt small: latest walks first, each note truncated.
    """
    queryset = (
        Walk.objects.select_related('dog', 'dog__client')
        .filter(date__gte=month_start, date__lte=month_end)
        .exclude(notes='')
        .order_by('-date')
    )
    if client is not None:
        queryset = queryset.filter(dog__client=client)
    lines = []
    for walk in queryset[:MAX_OBSERVATION_WALKS]:
        note = ' | '.join(walk.notes.splitlines())[:MAX_OBSERVATION_CHARS]
        lines.append(
            f'{walk.date:%d/%m} — {walk.dog.name} ({walk.dog.client.name}): '
            f'{note}'
        )
    return '\n'.join(lines) if lines else 'nenhuma observação registrada'


def run_monthly_analysis(analysis):
    """Run the analysis of one ``AIAnalysis`` record.

    Returns ``(result_text, input_summary)``. Months without data return
    the deterministic ``NO_DATA_MESSAGE`` without calling the LLM.
    Raises for invalid stored months and for LLM/API failures (the
    caller — ``ai.tasks.monthly_analysis_task`` — records and notifies).
    """
    parsed = parse_month(analysis.month)
    if parsed is None:
        raise ValueError(f'Mês inválido para análise: {analysis.month!r}')
    year, month = parsed
    month_start, month_end = month_bounds(year, month)
    client = analysis.client

    period = month_label(year, month)
    scope = (
        f'cliente {client.name}' if client is not None else 'todos os clientes'
    )

    rows, totals = monthly_control(
        month_start, month_end, client=client
    )
    if not rows:
        return NO_DATA_MESSAGE, NO_DATA_SUMMARY

    counters = _counters_text(rows, totals)
    observations = _observations_text(month_start, month_end, client=client)
    input_summary = (
        f'Período: {period}\nEscopo: {scope}\n\n{counters}\n\n'
        f'Observações: {observations}'
    )

    chain = MONTHLY_ANALYSIS_PROMPT | get_chat_model()
    response = chain.invoke(
        {
            'period': period,
            'scope': scope,
            'counters': counters,
            'observations': observations,
        }
    )
    return response.content, input_summary
