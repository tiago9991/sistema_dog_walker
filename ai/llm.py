"""Initial AI abstraction (PRD section 19 — Sprint 12).

Single integration point with the LLM stack: LangChain 1.x + OpenAI,
model ``gpt-5.5-mini`` (PRD section 7). Domain code (services/tasks)
builds models and runs chains through this module only, so provider and
model configuration never leaks into the domain — changing the model
or the provider later is a change here.

Configuration comes from settings (``OPENAI_API_KEY``/``AI_MODEL`` —
``.env`` locally, production environment/secrets per PRD sections 15
and 38). Without a key the AI features report "not configured" instead
of failing at call time (``ai_configured`` is checked at dispatch and
again inside the task).

LangGraph is installed as part of the stack (PRD section 7) and is the
escalation path for future use cases that need state, multiple steps,
branching, tools or retries — the escalation criteria are the PRD
section 19 principles themselves ("usar chamada simples ao LLM quando
uma chamada simples for suficiente"). The first use case is a single
LLM call over aggregated data, so no graph is built yet; see
``docs/ia.md`` for the decision rule and how a graph plugs into this
same abstraction.
"""

from django.conf import settings


def ai_configured():
    """Whether the LLM is configured (``OPENAI_API_KEY`` present)."""
    return bool(settings.OPENAI_API_KEY)


def get_chat_model():
    """Build the configured chat model (LangChain ``ChatOpenAI``).

    The heavy LangChain/OpenAI imports stay inside the function on
    purpose: the web process never calls the LLM (the Celery worker
    does — PRD section 19), so Django startup does not pay the import
    cost.
    """
    if not ai_configured():
        raise RuntimeError(
            'IA não configurada: defina OPENAI_API_KEY no ambiente.'
        )
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.AI_MODEL,
        api_key=settings.OPENAI_API_KEY,
    )
