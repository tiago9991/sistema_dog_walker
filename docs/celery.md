# Celery — tasks assíncronas e notificações

Implementado na **Sprint 11** (PRD seções 7, 17, 18 e RNF-004). Fonte de
verdade funcional: [PRD](./PRD.md).

## Stack

| Camada | Valor |
|---|---|
| Broker | RabbitMQ 4 (`rabbitmq:4-alpine`, serviço `rabbitmq`) |
| Result backend | Redis (`redis://redis:6379/0`, mesma instância do cache) |
| Cache | Redis via `REDIS_URL` (fallback: `LocMemCache` sem `REDIS_URL`) |
| Worker | serviço `celery-worker` (`celery -A core worker`) |
| Beat | serviço `celery-beat` (`celery -A core beat`) |
| Painel | `dj-celery-panel` 0.6 no Django Admin (`/admin/dj-celery-panel/`) |
| App Celery | `core/celery.py` (`celery_app`), tasks em `<app>.tasks` (autodiscover) |

## Configuração (`core/settings.py` + `core/celery.py`)

- `CELERY_BROKER_URL` — broker (vazio ⇒ `CELERY_TASK_ALWAYS_EAGER=True`:
  tasks rodam de forma **síncrona**, útil para *quick runs* no host sem
  RabbitMQ; o Compose/produção sempre definem o broker — fluxo real
  assíncrono).
- `REDIS_URL` — cache do Django **e** result backend do Celery
  (`CELERY_RESULT_BACKEND = REDIS_URL`; sem Redis não há backend — em modo
  eager os resultados ficam em memória). Nota: `django-cache` como result
  backend exigiria o pacote `django-celery-results` apenas para reusar o
  cache do Django — evitado de propósito.
- `CELERY_TIMEZONE = TIME_ZONE` (`America/Sao_Paulo`).
- **RabbitMQ ≥ 4.4**: o RabbitMQ 4.4 não permite mais filas transitórias
  **não-exclusivas** (feature flag `transient_nonexcl_queues` removida) e o
  Celery 5.6/kombu 5.6 ainda declara assim, por padrão, as filas de
  controle (pidbox) e de eventos (gossip/`celery events`). Correção em
  vigor: `CELERY_CONTROL_QUEUE_EXCLUSIVE = True` e
  `CELERY_EVENT_QUEUE_EXCLUSIVE = True` — filas transitórias **exclusivas**
  continuam suportadas (e combinam com a semântica: uma conexão consome a
  fila de cada hostname) e mantêm o ciclo de vida `auto_delete`/`x-expires`.
- Beat (`core/celery.py`): `generate-walks-daily` — todo dia às **03:00**
  `America/Sao_Paulo` (idempotente — PRD RF-005).

## Task atual

`walks.tasks.generate_walks_task(user_id=None)` (RF-005):

- envolvê `walks.services.generate_walks`;
- despachada pela interface (botão **"Gerar passeios"** em Passeios —
  `POST /walks/gerar/`, `walks.add_walk`) → notifica o solicitante ao
  concluir (RNF-004);
- agendada pelo Beat (sem usuário) → resultado apenas nos logs do worker
  (não há solicitante para notificar).

## Notificações (RNF-004)

Modelo `notifications.Notification` (decisão 13 da seção 53 do PRD):
in-app, por usuário (nível info/success/warning/error, título, mensagem,
link interno opcional, lida/não lida). Superfícies na interface:

- **sino no cabeçalho** (todas as páginas; badge de não lidas + últimas 5 +
  "marcar todas como lidas") — `notifications.context_processors`;
- **toasts + badge ao vivo** via `static/js/scsi.js`: polling em
  `/notifications/poll/` a cada 30s (e 4s enquanto há task pendente);
  "última vista" por aba (sessionStorage) evita re-toast de notificações
  antigas;
- **página `/notifications/`** com histórico paginado e "marcar como lida".

Fluxo RNF-004 do botão de geração (`data-async-task`):

1. submit interceptado (fetch) — **sem navegação**, interface utilizável;
2. botão entra em estado **loading** (spinner) até a conclusão;
3. resposta imediata com feedback ("iniciada em segundo plano…");
4. o worker executa e cria a **notificação** de conclusão → o polling exibe
   o toast e atualiza o badge, e o botão volta ao normal.

Validação real executada (Compose, Sprint 11): login → `POST /walks/gerar/`
respondeu em **~180 ms** enquanto o **worker** executou a task em outro
container (0,12 s) e criou a notificação com o resultado e link.

## Desenvolvimento (Docker Compose)

```powershell
docker compose up -d --build   # django + postgres + redis + rabbitmq + worker + beat
docker compose logs -f celery-worker celery-beat
```

- Entrypoints: web usa `scripts/entrypoint.py` (aguarda banco → advisory
  lock → migrations → collectstatic); worker/beat usam
  `scripts/celery_entrypoint.py` (**aguardam o banco, sem migrations e sem
  collectstatic** — PRD §17).
- Painel: `/admin/dj-celery-panel/` (restrito a staff; requer worker no ar
  para workers/filas).
- No host sem Compose: sem `CELERY_BROKER_URL`/`REDIS_URL` o modo eager
  mantém o botão e as notificações funcionando (síncrono).

## Pitfalls registados

- `CELERY_RESULT_BACKEND='django-cache'` sem o pacote `django-celery-results`
  → `ModuleNotFoundError` **no startup do worker** (tests passam porque no
  modo eager o backend nunca é instanciado) — validação real exige worker
  de verdade.
- RabbitMQ 4.4 + Celery 5.6 sem `CELERY_CONTROL_QUEUE_EXCLUSIVE` /
  `CELERY_EVENT_QUEUE_EXCLUSIVE` → crash-loop do worker
  (`Queue.declare: INTERNAL_ERROR transient_nonexcl_queues deprecated`).
- `django.core.cache.backends.redis.RedisCache` e o backend Redis do Celery
  exigem o pacote `redis` no `requirements.txt`.
