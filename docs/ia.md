# IA — análises com LangChain

Implementado na **Sprint 12** (PRD seções 7, 19, 9.1 e 53 — decisão 15).
Fonte de verdade funcional: [PRD](./PRD.md).

## Stack

| Camada | Valor |
|---|---|
| Framework | LangChain 1.4 (`langchain` + `langchain-core`) |
| Provedor | OpenAI via `langchain-openai` (`ChatOpenAI`) |
| Modelo | `gpt-5.5-mini` (setting `AI_MODEL` — PRD seção 7) |
| Orquestração | LangGraph 1.2 instalado — ver [LangGraph: quando usar](#langgraph-quando-usar) |
| Execução | Celery worker (`ai.tasks.monthly_analysis_task`) |
| Persistência | `ai.AIAnalysis` (tabela abaixo) |
| Notificação | `notifications.services.notify` (in-app, RNF-004) |

## Abstração inicial (`ai/llm.py`)

Ponto único de integração com o LLM: `ai_configured()` e
`get_chat_model()`. Nenhum módulo de domínio constrói provedores —
modelo/chave vêm das settings (`OPENAI_API_KEY`/`AI_MODEL`), e trocar de
modelo ou provedor no futuro é uma mudança só nesse módulo.

- Sem `OPENAI_API_KEY` as funcionalidades de IA **falham de forma
  clara**: "IA não configurada" no dispatch (antes de criar o registro) e
  erro persistido na task se a chave sumir entre o dispatch e a
  execução. Nada mais quebra.
- Os imports pesados do LangChain ficam **dentro** de
  `get_chat_model()`: o processo web nunca chama o LLM (quem chama é o
  worker), então o startup do Django não paga o custo do import.

## Caso de uso — Resumo operacional mensal

Primeiro caso de uso do MVP (decisão 15 da seção 53 do PRD): a IA
analisa **os mesmos contadores do controle mensal** (RF-011 — reusa
`walks.services.monthly_control`, então a análise nunca diverge da
página `/walks/controle/`) mais as observações registradas no mês
(RF-008/RF-013 — os motivos por trás de cancelamentos/não realizações),
para um mês (`?month=YYYY-MM`) e opcionalmente um cliente.

Saída (contrato do prompt): seções **Resumo / Destaques / Pontos de
atenção / Recomendações** em português do Brasil, sem inventar números e
sem afirmações financeiras (regras financeiras seguem abertas — seção
53).

Decisões de design:

- **Sem dados ⇒ sem chamada ao LLM**: meses sem passeios/programações
  retornam uma mensagem determinística (`ai.services.NO_DATA_MESSAGE`)
  — sem superfície de alucinação e sem gasto de chamada.
- **Sem tools**: o modelo recebe apenas contadores agregados e
  observações delimitadas (≤ 40 observações, ≤ 150 caracteres cada) —
  a IA nunca acessa o banco diretamente.
- **Snapshot preservado**: o texto exato enviado ao modelo é
  persistido em `AIAnalysis.input_summary` — a página de detalhe mostra
  o que a IA viu (auditoria/transparência).

## Fluxo assíncrono (RNF-004)

```
Interface (form data-async-task)          Worker Celery
──────────────────────────────           ─────────────────────────────
POST /ai/solicitar/
  ├─ IA configurada? não → 503 (msg)      monthly_analysis_task(id)
  ├─ valida mês (padrão: corrente)         ├─ run_monthly_analysis()
  ├─ cria AIAnalysis (running)             │    ├─ mens sem dados →
  ├─ monthly_analysis_task.delay(id) ───►  │    │   resultado determinístico
  └─ responde JSON: "iniciada em          │    └─ prompt | model (LLM)
     segundo plano…"                       ├─ mark_completed(result, snapshot)
                                           │   → notify success + link
                                           └─ (exceção) mark_failed(error)
                                               → notify error + link
```

1. o submit é interceptado (`static/js/scsi.js`) — **sem navegação**,
   botão em **loading**;
2. o request só cria o registro `running` e despacha (milissegundos);
3. o worker chama o LLM e persiste o resultado/erro;
4. a **notificação** de conclusão chega via polling → toast + badge, o
   botão volta ao normal e o link abre o resultado.

Sem broker (`CELERY_TASK_ALWAYS_EAGER`) a task roda de forma síncrona —
o fluxo da interface é o mesmo (PRD seção 18).

## Persistência (`ai.AIAnalysis`)

| Campo | Observação |
|---|---|
| `kind` | tipo da análise (`monthly_summary` — extensível) |
| `status` | `running` / `completed` / `failed` |
| `month` | `YYYY-MM` (escopo mensal) |
| `client` | FK opcional (`PROTECT`) — escopo reproduzível |
| `input_summary` | snapshot dos dados enviados ao modelo |
| `result` / `error` | texto resultante / motivo legível da falha |
| `requested_by` | FK `User` (`SET_NULL`) — a análise sobrevive ao usuário |
| `completed_at` | preenchida ao concluir (sucesso ou falha) |

Índices `(kind, -created_at)` e `(status, -created_at)`. Análises são
dados de negócio derivados de `walks`: o acesso é regido por
`walks.view_walk` (a mesma permissão do controle mensal de onde vêm os
dados) — grupos `Operação` e `Leitura` podem solicitá-las e lê-las.

## Prompt (`ai/prompts.py`)

`MONTHLY_ANALYSIS_PROMPT` (`ChatPromptTemplate`): mensagem de sistema
define o papel (analista operacional sênior do serviço), as regras (só
os dados fornecidos; informação ausente declarada; sem afirmações
financeiras) e o formato da resposta; a mensagem humana recebe
período, escopo, contadores por cachorro + totais e as observações do
mês. Prompts são artefatos de negócio versionados com o código.

## LangGraph: quando usar

O PRD seção 19 manda usar **chamada simples** quando ela é suficiente.
O resumo mensal é uma única chamada sobre dados agregados — sem estado,
sem branching, sem tools, sem retries além dos nativos do SDK — portanto
**nenhum grafo é criado** (um grafo aqui seria artificial). O LangGraph
1.2 está instalado e é o **caminho de escalação** quando um caso de uso
apresentar estado, múltiplas etapas, decisão, branching, ferramentas,
retries ou persistência (critérios do próprio PRD).

Quando isso acontecer, o grafo se pluga na mesma abstração — os nós
continuam usando `ai.llm.get_chat_model()`:

```python
from langgraph.graph import StateGraph, START, END

class MonthlySummaryState(TypedDict):  # exemplo esqueleto
    counters: str
    draft: str
    attempts: int

def analyze(state): ...
def review(state): ...   # decide: END ou re-analyze (retry/branching)

graph = StateGraph(MonthlySummaryState)
graph.add_node("analyze", analyze)
graph.add_node("review", review)
graph.add_edge(START, "analyze")
graph.add_edge("analyze", "review")
graph.add_conditional_edges("review", review, {"approve": END, "retry": "analyze"})
app = graph.compile()
```

## Configuração

```env
OPENAI_API_KEY=...   # .env local (gitignored) / ambiente de produção (PRD seções 15/38)
AI_MODEL=gpt-5.5-mini # PRD seção 7
```

Em produção o tráfego de saída para a OpenAI sai pela rede
`scsi_v1_egress` (PRD seções 11.2/50.4) — worker/beat, nunca pelo
`traefik_public`.

## Testes (`ai/tests.py`)

O LLM é **sempre mockado** (testes nunca chamam a OpenAI): o mock é um
callable que o LangChain embrulha como `RunnableLambda`, então o
caminho real (`prompt | model`) é executado. Cobertura: modelo
(`period_display` pt-br, transições de status), serviço (com dados/sem
dados — provando que sem dados o LLM não é chamado —, escopo por
cliente, mês inválido), task (conclusão + notificação com link, falha
persistida + notificação de erro, sem solicitante, registro sumido),
views (login/permissões, dispatch não-bloqueante com `delay` mockado,
não-configurada, falha de broker) e os pontos de entrada da interface.
