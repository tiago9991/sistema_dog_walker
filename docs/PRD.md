\
# PRD — Sistema de Gestão para Dog Walker Inteligente

**Documento:** Product Requirements Document  
**Projeto:** Sistema de Gestão para Dog Walker Inteligente  
**Versão:** 1.0  
**Status:** Baseline para desenvolvimento  
**Idioma da interface:** Português brasileiro  
**Idioma do código:** Inglês  
**Timezone:** `America/Sao_Paulo`  
**Domínio de produção:** `scsi.digital`  
**Registry da aplicação:** `ghcr.io/pycodebr/scsi_v1`

---

## 1. Objetivo do documento

Este PRD é o documento de referência funcional, técnico e operacional para o desenvolvimento do Sistema de Gestão para Dog Walker Inteligente.

Ele deve ser utilizado para:

- orientar o planejamento do projeto;
- definir o escopo funcional;
- orientar a arquitetura;
- orientar a implementação;
- organizar as sprints;
- definir critérios de aceite;
- orientar infraestrutura e deploy;
- documentar decisões técnicas;
- servir como checklist de evolução do sistema;
- reduzir decisões arbitrárias durante o desenvolvimento.

### 1.1 Regra de precedência

Quando houver conflito entre este PRD e uma decisão posterior explicitamente aprovada pelo responsável pelo projeto, a decisão posterior deve ser registrada neste documento antes de ser considerada parte da arquitetura oficial.

Quando houver dúvida sobre um requisito ainda não decidido, o desenvolvimento deve registrar o ponto como **Open Decision** em vez de inventar um comportamento de negócio.

---

# 2. Visão do produto

O sistema será uma aplicação web para gestão operacional de um trabalho de Dog Walker.

O produto deve permitir controlar:

- usuários;
- permissões;
- clientes;
- cachorros;
- programação de passeios;
- geração de passeios;
- execução dos passeios;
- cancelamentos;
- histórico;
- observações;
- controle mensal;
- dashboard;
- tarefas assíncronas;
- funcionalidades de IA;
- relatórios;
- dados de demonstração.

A aplicação deve ser construída com foco em simplicidade operacional: o usuário deve conseguir visualizar rapidamente quais passeios estão previstos, quais foram realizados, quais foram cancelados e quanto ainda falta realizar no período.

---

# 3. Objetivos do produto

## 3.1 Objetivos principais

1. Centralizar os dados dos clientes e cachorros.
2. Automatizar a geração dos passeios previstos.
3. Facilitar o registro de passeios realizados.
4. Permitir acompanhamento diário, semanal e mensal.
5. Permitir acompanhamento do contrato mensal de cada cliente/cachorro.
6. Manter histórico confiável dos passeios.
7. Fornecer dashboard operacional.
8. Criar base arquitetural para funcionalidades de IA.
9. Permitir processamento pesado em background sem bloquear a interface.
10. Disponibilizar infraestrutura pronta para produção em Docker Swarm.

## 3.2 Não objetivos da primeira versão

Os seguintes itens não fazem parte do escopo inicial, salvo solicitação posterior:

- aplicativo mobile nativo;
- integração com gateways de pagamento;
- emissão fiscal;
- marketplace;
- geolocalização em tempo real;
- rastreamento GPS do passeio;
- integração automática com WhatsApp;
- integração automática com calendário externo;
- multi-VPS;
- cluster Swarm multi-node como requisito inicial.

Esses itens podem ser registrados como evolução futura.

---

# 4. Usuários e perfis

O sistema deve utilizar o sistema nativo de usuários e autenticação do Django.

## 4.1 Usuário autenticado

Pode acessar os recursos para os quais possuir permissão.

## 4.2 Administrador

Perfil destinado à administração do sistema.

Deve possuir acesso administrativo conforme as permissões definidas no Django Admin.

## 4.3 Permissões

O sistema deve utilizar:

- usuários Django;
- grupos;
- permissões nativas;
- verificações no backend;
- decorators/mixins apropriados;
- filtragem de querysets pelo escopo de acesso.

A interface pode ocultar ações que o usuário não pode executar, mas isso nunca substitui a autorização no backend.

## 4.4 Modelo de autorização implementado (Sprint 3)

Autenticação:

- `/login/` e `/logout/` (logout exclusivamente via POST);
- páginas de autenticação próprias em pt-br, conforme o design system;
- toda rota de negócio exige login (`LoginRequiredMixin`/`@login_required`)
  e redireciona para `/login/?next=...`;
- `/health/` permanece público (seção 16).

Grupos (criados pela migration `base.0001_groups` e estendidos pela
`base.0002_walks_permissions`):

| Grupo | Permissões |
|---|---|
| `Operação` | `view`/`add`/`change` de `Client`, `Dog`, `WalkSchedule` e `Walk` |
| `Leitura` | `view` de `Client`, `Dog`, `WalkSchedule` e `Walk` |

Mapeamento de ações:

- CRUD de clientes e cachorros → permissões nativas `view_*`, `add_*`,
  `change_*` de cada model;
- desativação/reativação (soft) → `change_*`;
- `delete_*` não é concedido a grupo algum: o histórico deve ser preservado
  (RF-002/RF-003); remoção física só é possível no Django Admin;
- administração de usuários, grupos e permissões: Django Admin nativo
  (`/admin/`), restrito a `is_staff`.

Cachorros são acessíveis apenas sob o escopo do seu cliente
(`/clients/<client_pk>/dogs/...`), com querysets filtrados por `client_pk`
acesso por ID de outro escopo → 404 (RF-003).

---

# 5. Requisitos funcionais

## RF-001 — Gestão de usuários

O sistema deve permitir:

- cadastro de usuários;
- autenticação;
- login;
- logout;
- controle de permissões;
- administração de usuários;
- ativação/desativação quando aplicável.

### Critérios de aceite

- Usuário não autenticado não pode acessar áreas protegidas.
- Login válido cria sessão.
- Logout encerra a sessão.
- Permissões são verificadas no backend.
- Usuário sem permissão não consegue executar a ação apenas manipulando uma URL ou request.

---

## RF-002 — Gestão de clientes

O sistema deve permitir:

- cadastrar cliente;
- editar cliente;
- visualizar cliente;
- desativar cliente;
- listar clientes;
- pesquisar clientes;
- acessar os cachorros associados.

### Regras

A desativação deve preservar histórico.

Não apagar dados históricos simplesmente porque um cliente foi desativado.

### Critérios de aceite

- Cliente pode ser cadastrado.
- Cliente pode ser editado.
- Cliente pode ser visualizado.
- Cliente pode ser desativado.
- Dados históricos permanecem disponíveis.
- Clientes desativados não devem aparecer como opções operacionais quando a ação exigir somente clientes ativos.

---

## RF-003 — Gestão de cachorros

Cada cliente pode possuir múltiplos cachorros.

O sistema deve permitir:

- cadastrar cachorro;
- editar cachorro;
- visualizar cachorro;
- desativar cachorro;
- vincular cachorro a cliente;
- listar cachorros do cliente;
- consultar histórico do cachorro.

### Critérios de aceite

- Um cliente pode possuir zero, um ou vários cachorros.
- Cada cachorro pertence a um cliente.
- Não deve ser possível acessar um cachorro pertencente a outro escopo apenas alterando seu ID.
- O histórico do cachorro permanece disponível após desativação.

---

## RF-004 — Programação de passeios

O sistema deve permitir definir a programação de cada cachorro.

A programação deve contemplar:

- frequência;
- dias da semana;
- período aplicável;
- status da programação.

### Observação

O modelo definitivo de recorrência deve ser definido durante a implementação do domínio de programação.

Não assumir regras de cobrança ou prorrateamento que ainda não foram especificadas.

### Regras de recorrência implementadas (Sprint 6)

- Recorrência **semanal por dias da semana**: a programação seleciona os dias
  (segunda a domingo) em que o passeio ocorre; a frequência vigente é
  `semanal` (campo `frequency`, extensível a modelos futuros).
- Período aplicável: **início obrigatório** e **fim opcional** (vazio =
  aberto); o fim nunca pode ser anterior ao início.
- Status da programação: `ativa`/`desativada` (desativação soft, com
  `deactivated_at` — histórico preservado).
- Validações (model `clean`, válidas no app e no Admin): ao menos um dia da
  semana; período válido; duas programações ativas do mesmo cachorro não
  podem gerar passeios para o mesmo dia (bloqueio quando há dias da semana
  em comum com períodos sobrepostos).
- Programações não podem ser criadas para cachorro ou cliente desativado.

---

## RF-005 — Geração de passeios

O sistema deve gerar os passeios previstos de acordo com a programação cadastrada.

A geração deve ser determinística.

Deve evitar duplicação de passeios.

### Requisitos técnicos

- utilizar timezone `America/Sao_Paulo`;
- tratar datas corretamente;
- considerar alterações na programação;
- utilizar constraints/validações para evitar duplicidade quando aplicável;
- permitir execução segura em background quando o volume justificar.

### Regras de geração implementadas (Sprint 7)

- Algoritmo determinístico: para cada programação ativa (de cachorro e
  cliente ativos), percorre as datas da janela e cria o passeio quando o dia
  da semana coincide — no máximo **um passeio por cachorro por data**
  (`UniqueConstraint(dog, date)`).
- Janela de geração: **[hoje − 7 dias, hoje + 30 dias]** (padrão,
  configurável por execução via `--lookback`/`--horizon`); o retrospecto
  cobre execuções que não ocorreram sem criar passeios anteriores ao início
  da programação.
- Idempotência: criação via `get_or_create` + constraint; re-execuções não
  duplicam nem sobrescrevem passeios existentes (status preservado).
- Alterações de programação (criar/editar/ativar/desativar) fazem o
  **resync** do cachorro: apagam os futuros `previsto` e os regeneram pelas
  programações ativas; passeios com qualquer outro status nunca são apagados
  (histórico preservado). No resync, a janela alcança o início da
  **programação ativa mais antiga** do cachorro (decisão 26/10/2026 —
  seção 53): uma programação cadastrada depois do próprio início ainda gera
  os passeios passados contratados (que o retrospecto padrão de 7 dias não
  alcançaria) como `previsto`, para que possam receber desfecho
  (RF-007/RF-008) e entrar no controle mensal/relatório; o limite por
  programação continua garantindo que nenhum passeio seja criado anterior
  ao início dela.
- Timezone: datas operacionais obtidas com `timezone.localdate()`
  (`America/Sao_Paulo`); o passeio armazena `date` (sem horário).
- Execução: management command `generate_walks` (idempotente, com
  relatório). Task Celery não é necessária antes da Sprint 11 (o broker
  ainda não existe e o volume não justifica).

---

## RF-006 — Controle de passeios

O sistema deve permitir visualizar passeios:

- por dia;
- por semana;
- por mês.

Cada passeio deve possuir status operacional.

Estados mínimos previstos:

- previsto;
- realizado;
- cancelado;
- não realizado.

A máquina de estados definitiva deve ser documentada antes da implementação final.

### Máquina de estados implementada (Sprint 8)

| De | Para | Ação |
|---|---|---|
| `previsto` | `realizado` | confirmar passeio (RF-007) |
| `previsto` | `cancelado` | cancelar, com observação/motivo opcional (RF-008) |
| `previsto` | `não realizado` | registrar não realização, com observação/motivo opcional (RF-008) |
| `realizado` / `cancelado` / `não realizado` | `previsto` | reverter (correção de erro) |

Transições fora desta máquina são rejeitadas no backend (manipulação de
URL/request não bypassa). Toda transição registra `status_changed_at`;
observações são anexadas ao histórico do passeio com carimbo de data/hora.
Regras de impacto financeiro e de remarcação permanecem decisões abertas
(seção 53).

---

## RF-007 — Confirmação de passeio

O usuário deve conseguir marcar um passeio como realizado.

Ao realizar a confirmação:

- o status deve ser atualizado;
- a alteração deve permanecer registrada;
- o passeio deve entrar no histórico;
- os indicadores mensais devem refletir a alteração.

---

## RF-008 — Cancelamento e não realização

O sistema deve permitir registrar:

- cancelamento;
- passeio não realizado.

Quando aplicável, deve existir campo de observação/motivo.

As regras de impacto financeiro não devem ser inventadas nesta primeira especificação.

---

## RF-009 — Histórico

O sistema deve manter histórico dos passeios por cachorro.

O histórico deve permitir consultar:

- data;
- status;
- cliente;
- cachorro;
- observações;
- informações operacionais relevantes.

---

## RF-010 — Dashboard

O dashboard deve apresentar um resumo operacional.

Indicadores mínimos:

- quantidade de clientes;
- quantidade de cachorros;
- passeios previstos;
- passeios realizados;
- passeios restantes;
- informações por cliente/cachorro;
- indicadores mensais.

A implementação deve priorizar informações úteis para tomada de decisão operacional.

### Indicadores implementados (Sprint 10)

O dashboard é a página inicial da aplicação (`/`, nome de URL `home`;
login redireciona para ele). Indicadores:

- **clientes**: ativos/total (com barra de progresso e contagem de
  inativos);
- **cachorros**: ativos/total (idem);
- **passeios de hoje**: realizados/total do dia, pendentes
  (`previsto`), com lista dos passeios do dia (visão de passeios) e ação
  rápida de "realizar" para operadores;
- **visão mensal**: os seis contadores de RF-011 do mês
  (`?month=YYYY-MM`, padrão o mês corrente), com resumo por cliente
  (contratados/previstos/realizados/cancelados/não realizados/restantes +
  progresso) e link para o controle mensal completo.

Filtros relevantes: mês e cliente (escopam a visão mensal e a lista do
dia). Consultas: todas as contagens via agregações (`aggregate`/`annotate`
— sem queries por linha); os contadores mensais reutilizam
`walks.services.monthly_control` (Sprint 9). Interface 100% com o design
system (cards KPI, tabelas `table-responsive`, mini-métricas) e
responsividade herdada da grade do design system (`col-xxl-3 col-md-6`,
`col-6`, `table-responsive` — RNF-001).

---

## RF-011 — Controle mensal

O sistema deve apresentar, por cliente/cachorro:

- passeios contratados;
- passeios previstos;
- passeios realizados;
- passeios cancelados;
- passeios não realizados;
- passeios restantes.

### Regra

A definição exata de "restante" deve ser baseada na regra de negócio aprovada para o status de cada passeio.

Não assumir que cancelamento sempre reduz ou sempre mantém o saldo contratado.

### Regras de cálculo implementadas (Sprint 9 — decisão 7 da seção 53 resolvida)

Por cliente/cachorro, para um mês calendário (`?month=YYYY-MM`, padrão o
mês corrente, timezone `America/Sao_Paulo`):

| Contador | Regra |
|---|---|
| `contratados` | `Dog.monthly_walks_quota` quando preenchida (pacote mensal por quantidade, ex.: 15/mês com dias flexíveis — decisão 26/10/2026) **é** o contrato do mês, substituindo a derivação por calendário; sem quota: datas do mês cobertas por programações **ativas** do cachorro (dia da semana dentro do período) — determinístico a partir de RF-004, independente da janela de geração (meses futuros também possuem contrato) |
| `previstos` | passeios existentes no mês com status `previsto` |
| `realizados` | passeios existentes no mês com status `realizado` |
| `cancelados` | passeios existentes no mês com status `cancelado` |
| `não realizados` | passeios existentes no mês com status `não realizado` |
| `restantes` | `contratados − realizados − cancelados − não realizados`, nunca negativo |

Regra por status (saldo **operacional**; o impacto **financeiro** de
cancelamento permanece decisão aberta na seção 53):

- `realizado`, `não realizado` e `cancelado` **consomem** o contrato do mês
  (não serão executados);
- `previsto` segue pendente;
- datas contratadas ainda sem passeio gerado (fora da janela de geração)
  permanecem no saldo — "restantes" responde "quanto falta executar no mês
  para cumprir o contrato vigente";
- quando o contrato vigente encolhe (ex.: programação desativada após
  execuções), `restantes` é limitado a zero — os desfechos registrados
  permanecem visíveis nas contagens de status.

Pacote mensal por quantidade (decisão 26/10/2026 — motivação: contratos
do tipo "15 passeios/mês" com dias flexíveis não podem ser expressos por
recorrência de dias da semana; 3 dias fixos/semana geram 13–15+ datas
conforme o mês, e o relatório compartilhado com o cliente mostrava um
contratados que o cliente não reconhece):

- a quota substitui **integralmente** a derivação por calendário no mês
  (a programação segue gerando os passeios regulares; passeios avulsos
  adicionados para fechar a quantidade contam como `realizados`);
- entrega além do pacote: `restantes` limitado a zero e progresso acima
  de 100% (entregou além do contratado);
- v1 — quota é um valor fixo por cachorro: para meses parciais
  (programação/início no meio do mês, desativações) deixar vazio ou
  ajustar o valor; mudança de contrato atualiza o campo (relatórios
  antigos regenerados refletem o valor atual).

Visões: `/walks/controle/` agrupada por cliente com subtotais e uma linha
por cachorro (visão por cliente e por cachorro), filtros por
cliente/cachorro/mês, totais gerais do mês e progresso de realização do
contrato; acessível a partir do detalhe do cliente e do cachorro.

---

## RF-012 — Filtros

Deve ser possível filtrar passeios por:

- cliente;
- cachorro;
- data;
- mês;
- status.

Os filtros devem funcionar no backend e possuir consultas eficientes.

---

## RF-013 — Observações

O sistema deve permitir registrar observações relacionadas a um passeio.

As observações devem possuir controle de acesso conforme o escopo do objeto.

---

# 6. Requisitos não funcionais

## RNF-001 — Responsividade

A aplicação deve funcionar corretamente em:

- desktop;
- notebook;
- tablet;
- celular.

## RNF-002 — Segurança

O sistema deve:

- proteger rotas;
- aplicar autenticação;
- aplicar autorização;
- impedir acesso horizontal indevido;
- proteger dados de tenants/escopos diferentes;
- proteger arquivos privados;
- evitar exposição de secrets;
- utilizar HTTPS em produção;
- proteger CSRF;
- utilizar configurações seguras de sessão;
- validar dados no backend.

## RNF-003 — Performance

Deve evitar:

- N+1 queries;
- processamento pesado durante request;
- consultas repetitivas;
- consultas sem índices quando índices forem necessários;
- carregamento excessivo de registros.

Quando apropriado utilizar:

- `select_related`;
- `prefetch_related`;
- agregações;
- índices;
- paginação;
- cache;
- Celery.

## RNF-004 — Assincronicidade

Processamentos demorados não devem bloquear a interface.

Ao iniciar uma task:

1. botão deve apresentar loading;
2. usuário deve receber feedback;
3. interface deve continuar utilizável;
4. conclusão deve gerar notificação.

## RNF-005 — Resiliência

Serviços do Swarm devem possuir:

- restart policies;
- healthchecks;
- resource limits;
- resource reservations.

O serviço web deve possuir rollout `start-first` e rollback automático quando configurado.

---

# 7. Stack tecnológica

| Camada | Tecnologia |
|---|---|
| Linguagem | Python >3.13 |
| Framework | Django >6.0 |
| IA | LangChain >1.0 |
| Orquestração de agentes | LangGraph |
| LLM | GPT-5.5-mini via OpenAI |
| Banco | PostgreSQL |
| Tasks | Celery |
| Broker | RabbitMQ |
| Result backend | Redis |
| Cache | Redis |
| Web/Proxy | Traefik |
| TLS | Let's Encrypt |
| DNS challenge | Cloudflare DNS-01 |
| Container | Docker |
| Dev local | Docker Compose |
| Produção | Docker Swarm |
| Registry | GHCR |
| PDF | ReportLab + PyPDF |
| Documentação | MkDocs + Mermaid |

---

# 8. Arquitetura Django

## 8.1 Projeto principal

O projeto Django deve se chamar:

`core`

## 8.2 App base

Deve existir:

`base`

para recursos compartilhados e fundamentais.

## 8.3 Domínios

Os domínios devem ser separados em apps Django independentes.

A decomposição inicial sugerida é:

- `base`
- `clients`
- `dogs`
- `walks`
- `scheduling`
- `dashboard`
- `notifications`
- `ai`
- `reports`

A criação definitiva de cada app deve acompanhar a necessidade real do domínio. Não criar apps artificiais apenas para cumprir uma lista.

## 8.4 Estrutura esperada

```text
project/
├── core/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── base/
├── clients/
├── dogs/
├── walks/
├── scheduling/
├── dashboard/
├── notifications/
├── ai/
├── reports/
├── design_system/
│   └── design-system.html
├── docs/
├── scripts/
├── manage.py
├── requirements.txt
├── Dockerfile
├── compose.yml
├── stack.yml
├── .env.example
├── .gitignore
└── README.md
```

A estrutura pode ser ajustada durante a implementação caso o domínio demonstre necessidade diferente.

---

# 9. Banco de dados e entidades

## 9.1 Entidades principais

O modelo inicial deve contemplar:

### User

Utilizar usuário nativo do Django.

### Client

Representa o cliente do Dog Walker.

Campos de negócio definitivos (definidos na Sprint 4 — decisão 1 da seção 53 resolvida):

| Campo | Tipo | Observação |
|---|---|---|
| `name` | `CharField(150)` | obrigatório; pesquisável |
| `phone` | `CharField(20)` | opcional; pesquisável |
| `email` | `EmailField` | opcional; pesquisável |
| `notes` | `TextField` | opcional |
| `is_active` | `BooleanField` | desativação soft; histórico preservado |
| `deactivated_at` | `DateTimeField` | preenchido na desativação |

Campos técnicos obrigatórios:

- `created_at`
- `updated_at`

### Dog

Representa um cachorro.

Relacionamento:

`Dog -> Client` (`ForeignKey`, `on_delete=PROTECT`, `related_name="dogs"`)

Um cliente pode possuir vários cachorros.

Campos de negócio definitivos (definidos na Sprint 5 — decisão 2 da seção 53 resolvida; `monthly_walks_quota` adicionada por decisão de 26/10/2026 — RF-011):

| Campo | Tipo | Observação |
|---|---|---|
| `name` | `CharField(150)` | obrigatório |
| `breed` | `CharField(100)` | opcional |
| `notes` | `TextField` | opcional |
| `monthly_walks_quota` | `PositiveSmallIntegerField` | opcional (≥1); pacote mensal por quantidade — vazio = contratados derivados das programações |
| `is_active` | `BooleanField` | desativação soft; histórico preservado |
| `deactivated_at` | `DateTimeField` | preenchido na desativação |

Campos técnicos:

- `created_at`
- `updated_at`

### WalkSchedule

Representa a programação recorrente.

Deve possuir vínculo com cachorro e informações necessárias para gerar passeios.

Campos definitivos (definidos na Sprint 6 — decisão 8 da seção 53 resolvida):

| Campo | Tipo | Observação |
|---|---|---|
| `dog` | `ForeignKey(Dog, PROTECT)` | `related_name="schedules"` |
| `frequency` | `CharField(20)` com choices | `semanal` (extensível) |
| `monday`..`sunday` | 7 `BooleanField` | dias da semana da recorrência |
| `start_date` | `DateField` | início do período (obrigatório) |
| `end_date` | `DateField` opcional | vazio = período aberto |
| `is_active` | `BooleanField` | desativação soft |
| `deactivated_at` | `DateTimeField` | preenchida na desativação |

Campos técnicos: `created_at`/`updated_at` (herdados de `BaseModel`).
Validações e regras de recorrência: ver RF-004.

### Walk

Representa um passeio previsto/realizado/cancelado.

Campos definitivos (definidos na Sprint 7 — decisões 3 e 4 da seção 53
resolvidas): **um passeio por cachorro por data**
(`UniqueConstraint(dog, date)`), sem componente de horário.

| Campo | Tipo | Observação |
|---|---|---|
| `dog` | `ForeignKey(Dog, PROTECT)` | `related_name="walks"` |
| `date` | `DateField` | data operacional (`America/Sao_Paulo`) |
| `status` | `CharField(20)` com choices | previsto/realizado/cancelado/não realizado |
| `notes` | `TextField` | observações; transições anexam entradas com data/hora |
| `status_changed_at` | `DateTimeField` | última transição de status |

Campos técnicos: `created_at`/`updated_at` (herdados de `BaseModel`).
Máquina de estados e regras de geração: ver RF-005/RF-006.

### Notification

Representa notificações para o usuário quando necessário.

Modelo definitivo (definido na Sprint 11 — decisão 13 da seção 53
resolvida): **in-app**, por usuário (sem e-mail/push no MVP), criada por
tasks de background ao concluírem (RNF-004).

| Campo | Tipo | Observação |
|---|---|---|
| `recipient` | `ForeignKey(User, CASCADE)` | `related_name="notifications"`; dado pessoal — some com o usuário |
| `level` | `CharField(20)` com choices | info/sucesso/atenção/erro (padrão: info) |
| `title` | `CharField(150)` | obrigatório |
| `message` | `TextField` | opcional |
| `link` | `CharField(200)` | caminho interno opcional (ex.: `/walks/dia/`); criado por tasks |
| `is_read` | `BooleanField` | leitura por destinatário |
| `read_at` | `DateTimeField` | preenchida ao ler |

Campos técnicos: `created_at`/`updated_at` (herdados de `BaseModel`).
Índices `(recipient, -created_at)` e `(recipient, is_read)`. Exposição na
interface: sino no cabeçalho (badge + últimas 5), toasts via polling
(`static/js/scsi.js` → `/notifications/poll/`) e página `/notifications/`.
Notificações são pessoais: todo queryset filtrado por `request.user`.

### AIAnalysis

Persistência definitiva dos resultados de IA (definida na Sprint 12,
quando o primeiro caso de uso foi implementado): um registro por
execução, criado no dispatch (`running`) e atualizado pela task Celery
com o resultado ou o motivo da falha.

| Campo | Tipo | Observação |
|---|---|---|
| `kind` | `CharField(20)` com choices | tipo da análise (`monthly_summary` — extensível) |
| `status` | `CharField(20)` com choices | `running`/`completed`/`failed` (padrão: `running`) |
| `month` | `CharField(7)` | `YYYY-MM` (escopo mensal) |
| `client` | `ForeignKey(Client, PROTECT)` opcional | escopo reproduzível |
| `input_summary` | `TextField` | snapshot dos dados enviados ao modelo (auditoria) |
| `result` | `TextField` | texto resultante |
| `error` | `TextField` | motivo legível da falha |
| `requested_by` | `ForeignKey(User, SET_NULL)` opcional | a análise sobrevive ao usuário (histórico) |
| `completed_at` | `DateTimeField` | preenchida ao concluir (sucesso ou falha) |

Campos técnicos: `created_at`/`updated_at` (herdados de `BaseModel`).
Índices `(kind, -created_at)` e `(status, -created_at)`. Arquitetura de
IA, prompt e fluxo assíncrono: [docs/ia.md](./ia.md).

---

# 10. Integridade de dados

A aplicação deve utilizar:

- `ForeignKey`;
- constraints;
- índices;
- `UniqueConstraint` quando necessário;
- validação de domínio;
- transações.

A geração de passeios deve ser idempotente.

Uma segunda execução do processo não pode criar duplicatas.

---

# 11. Arquitetura de infraestrutura

## 11.1 Serviços

```text
                    Internet
                       |
                    Cloudflare
                       |
                    Traefik
                       |
                traefik_public
                       |
                    Django App
                       |
              scsi_v1_internal
             /       |       \
        PostgreSQL  Redis   RabbitMQ
                              |
                         Celery Worker
                              |
                         Celery Beat
                              |
                       scsi_v1_egress
                              |
                         APIs externas
```

## 11.2 Redes

### `traefik_public`

- overlay;
- external;
- entrada HTTP/HTTPS;
- Traefik;
- Django app.

### `scsi_v1_internal`

- overlay;
- `internal: true`;
- comunicação interna;
- Django;
- PostgreSQL;
- Redis;
- RabbitMQ;
- Celery Worker;
- Celery Beat.

### `scsi_v1_egress`

- overlay;
- saída para internet;
- Celery Worker;
- Celery Beat;
- APIs externas.

Celery Worker e Celery Beat **não devem** estar em `traefik_public`.

---

# 12. Persistência

Devem existir volumes nomeados para:

- PostgreSQL;
- Redis;
- RabbitMQ;
- media;
- staticfiles;
- Let's Encrypt.

A estratégia definitiva de armazenamento de media deve considerar o fato de que o Swarm pode mover containers entre nodes. Para uma instalação inicial single-node, volume local é aceitável conforme o escopo atual; em expansão multi-node, storage compartilhado ou estratégia equivalente deverá ser definida.

---

# 13. TLS e Cloudflare

O certificado deve cobrir:

- `scsi.digital`;
- `*.scsi.digital`.

O desafio obrigatório é:

`DNS-01`

O provider é:

Cloudflare.

O token deve possuir o menor escopo necessário para a zona `scsi.digital`.

O token deve ser armazenado como:

`CLOUDFLARE_DNS_API_TOKEN`

em Docker Secret.

O Traefik deve ler:

```text
/run/secrets/CLOUDFLARE_DNS_API_TOKEN
```

por meio de:

```text
CF_DNS_API_TOKEN_FILE=/run/secrets/CLOUDFLARE_DNS_API_TOKEN
```

---

# 14. Configuração de produção

Valores-base:

```env
DEBUG=False

ALLOWED_HOSTS=scsi.digital,.scsi.digital,localhost,127.0.0.1

CSRF_TRUSTED_ORIGINS=https://scsi.digital,https://*.scsi.digital
```

`ALLOWED_HOSTS` deve conter somente hostnames.

`CSRF_TRUSTED_ORIGINS` deve conter URLs com esquema.

O `.env` de produção deve ficar fora do Git.

---

# 15. Secrets

Secret obrigatório:

```text
CLOUDFLARE_DNS_API_TOKEN
```

Demais credenciais sensíveis devem preferir Docker Secrets quando possível.

Exemplos de secrets que podem ser adotados conforme a implementação:

- PostgreSQL password;
- RabbitMQ password;
- outros tokens de serviços externos;
- chaves privadas ou credenciais de produção que não precisem estar em `.env`.

Não duplicar secrets em múltiplos mecanismos sem necessidade.

---

# 16. Healthchecks

## Django

Endpoint:

```text
/health/
```

Requisitos:

- HTTP 200;
- sem autenticação;
- sem acesso ao banco;
- processamento mínimo.

## PostgreSQL

Utilizar:

```bash
pg_isready
```

## Redis

Utilizar:

```bash
redis-cli ping
```

## RabbitMQ

Utilizar:

```bash
rabbitmq-diagnostics check_port_connectivity
```

Os `start_period` devem ser suficientemente grandes para evitar falsos negativos durante inicialização.

---

# 17. Inicialização e migrations

O entrypoint do Django deve:

1. aguardar o banco;
2. adquirir advisory lock PostgreSQL;
3. executar migrations;
4. liberar o lock;
5. executar `collectstatic --clear`;
6. iniciar a aplicação.

Celery Worker e Beat:

1. aguardam o banco;
2. não executam migrations;
3. não executam collectstatic.

O Swarm não deve depender de `depends_on` para garantir disponibilidade.

---

# 18. Celery

## Worker

Responsável por tarefas assíncronas.

## Beat

Responsável por tarefas agendadas.

## Broker

RabbitMQ.

## Result backend/cache

Redis.

## Painel

Utilizar `dj-celery-panel` no Django Admin.

### Implementação (Sprint 11)

- App Celery em `core/celery.py` (`celery_app`), tasks em `<app>.tasks`
  (autodiscover); configuração pelo namespace `CELERY_` das settings.
- Worker e Beat rodam como serviços do Compose
  (`celery-worker`/`celery-beat`) via `scripts/celery_entrypoint.py`
  (aguardam o banco; **sem** migrations/collectstatic — PRD 17).
- Result backend: a própria URL Redis (`REDIS_URL`) — `django-cache` foi
  evitado (exigiria `django-celery-results` apenas para reusar o cache).
- Sem `CELERY_BROKER_URL` (quick runs sem RabbitMQ) as tasks rodam de
  forma síncrona (`CELERY_TASK_ALWAYS_EAGER`) — Compose/produção sempre
  definem o broker (fluxo assíncrono real).
- RabbitMQ ≥ 4.4 removeu filas transitórias **não-exclusivas**; filas de
  controle/eventos do Celery 5.6 declaradas como **exclusivas**
  (`CELERY_CONTROL_QUEUE_EXCLUSIVE`/`CELERY_EVENT_QUEUE_EXCLUSIVE`).
- Beat: `generate-walks-daily` — todo dia 03:00 `America/Sao_Paulo`
  (idempotente, RF-005).
- Painel: `dj-celery-panel` + `dj_control_room_base` em `/admin/`
  (`/admin/dj-celery-panel/`, restrito a staff; sem tabelas/migrations).
- Detalhes operacionais e pitfalls: [docs/celery.md](./celery.md).

---

# 19. IA

Os agentes devem utilizar:

- LangChain >1.0;
- LangGraph;
- OpenAI;
- GPT-5.5-mini.

## Princípios

Usar chamada simples ao LLM quando uma chamada simples for suficiente.

Usar LangGraph quando existir:

- estado;
- múltiplas etapas;
- decisão;
- branching;
- ferramentas;
- retries;
- persistência;
- workflow complexo.

Processamentos de IA demorados devem ser executados via Celery.

### Implementação (Sprint 12)

- Stack em vigor: LangChain 1.4 + `langchain-openai` (OpenAI) com
  `gpt-5.5-mini` (`OPENAI_API_KEY`/`AI_MODEL` — seções 38/15); LangGraph
  1.2 instalado como caminho de escalação (ver abaixo).
- **Primeiro caso de uso (decisão 15 da seção 53): resumo operacional
  mensal** — a IA analisa os contadores de RF-011 (reusa
  `walks.services.monthly_control` — a análise nunca diverge da página
  de controle) e as observações do mês (RF-008/RF-013), por mês e
  opcionalmente por cliente. Saída em seções Resumo/Destaques/Pontos de
  atenção/Recomendações, com prompt especializado em pt-br (sem números
  inventados; sem afirmações financeiras — regras financeiras seguem
  abertas na seção 53).
- Abstração inicial (`ai/llm.py`): ponto único de construção do modelo;
  sem `OPENAI_API_KEY` as análises reportam "não configurada" e nada
  mais quebra.
- **LangGraph: nenhum workflow criado** — o resumo mensal é uma única
  chamada ao LLM (princípio desta seção); os critérios de escalação
  (estado, múltiplas etapas, decisão, branching, ferramentas, retries) e
  como um grafo se pluga na mesma abstração estão documentados em
  [docs/ia.md](./ia.md).
- Execução: `ai.tasks.monthly_analysis_task` via Celery (o LLM nunca
  roda no request), com persistência em `AIAnalysis` (seção 9.1) e
  notificação de conclusão ao solicitante com link para o resultado
  (RNF-004 — mesmo fluxo `data-async-task` da Sprint 11). Meses sem
  dados retornam mensagem determinística sem chamar o LLM.
- Interface: `/ai/` (histórico + formulário mês/cliente, registro
  `Em execução`, detalhe com resultado e snapshot dos dados
  considerados) e botão "Analisar com IA" no controle mensal (com os
  filtros do mês/cliente).
- Detalhes e pitfalls: [docs/ia.md](./ia.md).

---

# 20. Design system

O arquivo:

```text
design_system/design-system.html
```

é a referência visual oficial.

A implementação deve respeitar:

- cores;
- tipografia;
- componentes;
- espaçamentos;
- estados;
- padrões de interação.

Não criar estilos que contradigam o design system.

---

# 21. Relatórios

Utilizar:

- ReportLab;
- PyPDF.

Os relatórios devem ser gerados de maneira não bloqueante quando a geração puder ser demorada.

### Implementação (Sprint 13)

- Primeiro relatório: **controle mensal em PDF**
  (`/reports/controle-mensal/` — mesmos contadores e filtros da página
  `/walks/controle/`, reusando `walks.services.monthly_control`), com
  botão "Baixar PDF" na página de controle.
- Layout A4 paisagem: subtotais por cliente, totais gerais, zebra,
  cabeçalho repetido a cada página e rodapé com carimbo de geração em
  `America/Sao_Paulo` + paginação; cores do design system (seção 20);
  português com as fontes internas (Helvetica/WinAnsi — sem fontes
  embutidas).
- **Geração síncrona**: o relatório é agregado (as mesmas queries da
  página — RNF-003) e rápido, então o download responde direto com o
  PDF; a exigência não bloqueante ("quando a geração puder ser demorada")
  fica coberta pelo padrão assíncrono das Sprints 11/12 caso um
  relatório lento surja.
- PyPDF: validação dos documentos gerados (testes extraem o texto e
  comparam conteúdo pt-br/fuso horário) e ferramenta de inspeção.
- **Coluna "Dias realizados"** (decisão aprovada em 26/10/2026, após a
  Sprint 13): o PDF lista, por cachorro, os dias do mês em que o passeio
  foi realizado (números de dia; sem realizados → `—`) — fatos
  registrados (`Walk.date`/`status=realizado`) via
  `walks.services.completed_walk_dates_by_dog` (uma query agregada,
  índice `(status, date)`), sem N+1; contadores RF-011 inalterados.
- **PDF sem as colunas "Previstos", "Cancelados" e "Não
  realizados"** (decisão aprovada em 26/10/2026, após a Sprint 13): o
  PDF é o relatório compartilhado com o cliente final — apresenta
  apenas contratados/realizados/restantes + % de realização + dias
  realizados. A página `/walks/controle/` mantém os contadores
  completos; ambos usam o mesmo serviço de dados, portanto não
  divergem.
- Detalhes: [docs/relatorios.md](./relatorios.md).

---

# 22. Dados fake

Criar Django management command para carga de dados fictícios.

O comando deve produzir:

- múltiplos clientes;
- múltiplos cachorros;
- diferentes programações;
- diferentes datas;
- diferentes status;
- cenários variados.

Os dados devem ser claramente fictícios.

---

# 23. Documentação

A pasta:

```text
docs/
```

deve permanecer atualizada.

Utilizar MkDocs.

Documentar:

- arquitetura;
- instalação;
- desenvolvimento;
- domínio;
- banco;
- Celery;
- IA;
- Docker;
- Swarm;
- deploy;
- backup;
- troubleshooting;
- decisões arquiteturais.

Diagramas Mermaid devem ser utilizados quando agregarem valor.

---

# 24. Scripts operacionais

## `scripts/deploy.sh`

Responsabilidades:

- validar pré-condições;
- carregar `.env` com parser seguro;
- validar Swarm;
- validar secrets;
- validar redes;
- validar `DEBUG=False`;
- executar `git pull`;
- build;
- push para GHCR;
- deploy do stack;
- forçar rollout;
- verificar estado.

Deve existir:

```bash
--skip-build
```

## `scripts/backup.sh`

Responsabilidades:

- backup PostgreSQL;
- backup media;
- rotação;
- validação mínima;
- documentação de restauração.

---

# 25. Observabilidade e troubleshooting

O projeto deve possuir comandos documentados para:

```bash
docker node ls
docker stack ls
docker stack services <STACK>
docker stack ps <STACK>
docker service ls
docker service ps <SERVICE>
docker service logs <SERVICE>
docker network ls
docker secret ls
docker volume ls
```

Também deve existir documentação de diagnóstico para:

- container em restart loop;
- banco indisponível;
- RabbitMQ indisponível;
- Redis indisponível;
- healthcheck falhando;
- certificado não emitido;
- DNS challenge falhando;
- imagem não sendo puxada do GHCR;
- migration falhando;
- staticfiles ausentes;
- rollout com rollback.

---

# 26. Estratégia de desenvolvimento

O desenvolvimento deve ocorrer em pequenos incrementos.

Cada tarefa deve:

1. possuir objetivo claro;
2. alterar somente o necessário;
3. manter compatibilidade com o restante do sistema;
4. incluir migration quando necessário;
5. atualizar documentação quando necessário;
6. executar verificações técnicas;
7. registrar decisões importantes.

---

# 27. Sprints

## Sprint 0 — Fundação e planejamento

- [x] Confirmar requisitos funcionais.
- [x] Confirmar requisitos não funcionais.
- [x] Registrar decisões abertas.
- [x] Definir escopo do MVP.
- [x] Criar repositório Git.
- [x] Criar `.gitignore`.
- [x] Criar estrutura inicial do projeto.
- [x] Criar ambiente `.venv`.
- [x] Definir `requirements.txt`.
- [x] Criar projeto Django `core`.
- [x] Criar app `base`.
- [x] Configurar timezone `America/Sao_Paulo`.
- [x] Configurar idioma `pt-br`.
- [x] Criar `.env.example`.
- [x] Criar documentação inicial em `docs/`.
- [x] Registrar decisões arquiteturais iniciais.

## Sprint 1 — Django + PostgreSQL

- [x] Configurar PostgreSQL local.
- [x] Configurar conexão via `.env`.
- [x] Criar configuração de banco.
- [x] Criar modelo base com timestamps.
- [x] Criar estratégia de migrations.
- [x] Executar primeira migration.
- [x] Validar conexão.
- [x] Configurar Django Admin.
- [x] Documentar banco.

## Sprint 2 — Docker local

- [x] Criar Dockerfile.
- [x] Criar Compose local.
- [x] Configurar serviço Django.
- [x] Configurar PostgreSQL.
- [x] Configurar Redis.
- [x] Configurar RabbitMQ.
- [x] Configurar volumes.
- [x] Configurar healthchecks locais.
- [x] Validar subida completa.
- [x] Documentar comandos de desenvolvimento.

## Sprint 3 — Autenticação e permissões

- [x] Configurar login.
- [x] Configurar logout.
- [x] Criar páginas de autenticação.
- [x] Configurar proteção de rotas.
- [x] Definir grupos.
- [x] Definir permissões.
- [x] Configurar permissões no Admin.
- [x] Validar acesso não autorizado.
- [x] Documentar modelo de autorização.

## Sprint 4 — Clientes

- [x] Criar app/domain de clientes.
- [x] Criar model Client.
- [x] Criar migration.
- [x] Criar Admin.
- [x] Criar formulário.
- [x] Criar criação.
- [x] Criar edição.
- [x] Criar visualização.
- [x] Criar listagem.
- [x] Criar pesquisa.
- [x] Criar desativação.
- [x] Aplicar permissões.
- [x] Validar isolamento de dados.

## Sprint 5 — Cachorros

- [x] Criar model Dog.
- [x] Relacionar Dog com Client.
- [x] Criar migration.
- [x] Criar CRUD.
- [x] Criar interface dentro do cliente.
- [x] Implementar múltiplos cachorros.
- [x] Implementar desativação.
- [x] Criar histórico básico.
- [x] Validar isolamento.

## Sprint 6 — Programação

- [x] Definir modelo definitivo de programação.
- [x] Definir frequência.
- [x] Definir dias da semana.
- [x] Definir período de validade.
- [x] Criar model de programação.
- [x] Criar migration.
- [x] Criar CRUD.
- [x] Criar validações.
- [x] Documentar regras de recorrência.

## Sprint 7 — Geração de passeios

- [x] Definir algoritmo de geração.
- [x] Definir janela de geração.
- [x] Definir comportamento em alterações de programação.
- [x] Criar model Walk.
- [x] Criar statuses.
- [x] Criar constraints contra duplicidade.
- [x] Implementar geração.
- [x] Validar timezone.
- [x] Criar command de geração.
- [x] Criar task Celery quando necessário.
- [x] Validar idempotência.

## Sprint 8 — Operação dos passeios

- [x] Criar listagem diária.
- [x] Criar visão semanal.
- [x] Criar visão mensal.
- [x] Criar filtro por cliente.
- [x] Criar filtro por cachorro.
- [x] Criar filtro por data.
- [x] Criar filtro por mês.
- [x] Criar filtro por status.
- [x] Criar ação realizado.
- [x] Criar ação cancelado.
- [x] Criar ação não realizado.
- [x] Criar observações.
- [x] Criar histórico.

## Sprint 9 — Controle mensal

- [x] Definir regra de cálculo.
- [x] Implementar passeios contratados.
- [x] Implementar previstos.
- [x] Implementar realizados.
- [x] Implementar cancelados.
- [x] Implementar não realizados.
- [x] Implementar restantes.
- [x] Criar visão por cliente.
- [x] Criar visão por cachorro.
- [x] Validar cálculos com dados fake.

## Sprint 10 — Dashboard

- [x] Definir indicadores.
- [x] Criar consultas agregadas.
- [x] Otimizar queries.
- [x] Criar cards.
- [x] Criar visão de passeios.
- [x] Criar visão mensal.
- [x] Criar filtros relevantes.
- [x] Aplicar design system.
- [x] Validar responsividade.

## Sprint 11 — Notificações e background

- [x] Configurar Celery.
- [x] Configurar RabbitMQ.
- [x] Configurar Redis.
- [x] Configurar Worker.
- [x] Configurar Beat.
- [x] Configurar `dj-celery-panel`.
- [x] Criar modelo de notificação.
- [x] Criar feedback de loading.
- [x] Criar conclusão de task.
- [x] Criar notificação na interface.
- [x] Validar que requests não ficam bloqueados.

## Sprint 12 — IA

- [x] Configurar OpenAI.
- [x] Configurar LangChain.
- [x] Configurar LangGraph.
- [x] Configurar GPT-5.5-mini.
- [x] Criar abstração inicial de IA.
- [x] Definir primeiro caso de uso.
- [x] Criar prompt especializado.
- [x] Criar workflow LangGraph quando necessário.
- [x] Criar task Celery.
- [x] Persistir resultado quando necessário.
- [x] Criar notificação de conclusão.
- [x] Documentar arquitetura de IA.

## Sprint 13 — Relatórios

- [x] Configurar ReportLab.
- [x] Configurar PyPDF.
- [x] Criar primeiro relatório.
- [x] Criar layout.
- [x] Validar português.
- [x] Validar timezone.
- [x] Implementar geração assíncrona se necessário.
- [x] Documentar relatórios.

## Sprint 14 — Dados de demonstração

- [ ] Criar management command.
- [ ] Criar clientes fake.
- [ ] Criar cachorros fake.
- [ ] Criar programações.
- [ ] Criar passeios.
- [ ] Criar múltiplos status.
- [ ] Criar datas variadas.
- [ ] Criar cenários úteis para demonstração.
- [ ] Documentar comando.

## Sprint 15 — Segurança

- [ ] Revisar autenticação.
- [ ] Revisar autorização.
- [ ] Revisar isolamento de dados.
- [ ] Revisar acesso por ID.
- [ ] Revisar media.
- [ ] Revisar CSRF.
- [ ] Revisar sessões.
- [ ] Revisar secrets.
- [ ] Revisar DEBUG.
- [ ] Revisar ALLOWED_HOSTS.
- [ ] Revisar CSRF_TRUSTED_ORIGINS.
- [ ] Revisar permissões.
- [ ] Revisar exposição de serviços.

## Sprint 16 — Performance

- [ ] Executar Django system checks.
- [ ] Revisar N+1 queries.
- [ ] Adicionar `select_related` quando necessário.
- [ ] Adicionar `prefetch_related` quando necessário.
- [ ] Revisar índices.
- [ ] Revisar paginação.
- [ ] Revisar queries do dashboard.
- [ ] Revisar filtros.
- [ ] Revisar tasks assíncronas.
- [ ] Revisar cache.

## Sprint 17 — Produção Docker

- [ ] Criar stack de produção.
- [ ] Configurar Traefik.
- [ ] Configurar PostgreSQL.
- [ ] Configurar Redis.
- [ ] Configurar RabbitMQ.
- [ ] Configurar Celery Worker.
- [ ] Configurar Celery Beat.
- [ ] Configurar volumes.
- [ ] Configurar redes.
- [ ] Configurar secrets.
- [ ] Configurar healthchecks.
- [ ] Configurar restart policies.
- [ ] Configurar resource limits.
- [ ] Configurar update strategy.
- [ ] Configurar rollback.

## Sprint 18 — GHCR

- [ ] Criar imagem de produção.
- [ ] Configurar tagging.
- [ ] Validar build.
- [ ] Autenticar GHCR.
- [ ] Publicar imagem.
- [ ] Validar pull da imagem.
- [ ] Documentar processo.

## Sprint 19 — VPS

- [ ] Provisionar Ubuntu.
- [ ] Atualizar sistema.
- [ ] Configurar usuário administrativo.
- [ ] Configurar SSH.
- [ ] Configurar firewall.
- [ ] Instalar Docker.
- [ ] Inicializar Swarm.
- [ ] Criar redes.
- [ ] Criar secrets.
- [ ] Configurar `.env`.
- [ ] Clonar projeto.
- [ ] Configurar DNS.
- [ ] Fazer primeiro deploy.
- [ ] Validar healthchecks.
- [ ] Validar Traefik.
- [ ] Validar certificado.
- [ ] Validar aplicação.

## Sprint 20 — Deploy automatizado

- [ ] Criar `scripts/deploy.sh`.
- [ ] Criar parser seguro de `.env`.
- [ ] Criar validações de pré-condições.
- [ ] Implementar `git pull`.
- [ ] Implementar build.
- [ ] Implementar push GHCR.
- [ ] Implementar stack deploy.
- [ ] Implementar rollout.
- [ ] Implementar `--skip-build`.
- [ ] Implementar verificações pós-deploy.

## Sprint 21 — Backup e recuperação

- [ ] Criar `scripts/backup.sh`.
- [ ] Backup PostgreSQL.
- [ ] Backup media.
- [ ] Implementar rotação.
- [ ] Documentar restauração PostgreSQL.
- [ ] Documentar restauração media.
- [ ] Testar processo de restauração.

## Sprint 22 — Documentação final

- [ ] Revisar README.
- [ ] Revisar arquitetura.
- [ ] Revisar instalação.
- [ ] Revisar desenvolvimento.
- [ ] Revisar deploy.
- [ ] Revisar backup.
- [ ] Revisar troubleshooting.
- [ ] Revisar IA.
- [ ] Revisar domínio.
- [ ] Revisar Mermaid.
- [ ] Publicar documentação MkDocs.

## Sprint 23 — Hardening e Go-Live

- [ ] Executar checklist de segurança.
- [ ] Executar checklist de infraestrutura.
- [ ] Executar checklist funcional.
- [ ] Validar todos os healthchecks.
- [ ] Validar TLS.
- [ ] Validar renovação do certificado.
- [ ] Validar logs.
- [ ] Validar rollback.
- [ ] Validar backup.
- [ ] Validar restauração.
- [ ] Validar deploy sem downtime.
- [ ] Validar responsividade.
- [ ] Validar fluxo completo do usuário.
- [ ] Registrar versão de produção.
- [ ] Criar procedimento de operação.

---

# 28. Guia de deploy — VPS Ubuntu do zero

> Este capítulo é um runbook operacional. Os comandos devem ser executados com atenção e adaptados somente nos pontos explicitamente indicados.

## 28.1 Pré-requisitos

Antes de começar:

- VPS Ubuntu suportada pelo Docker;
- acesso SSH;
- domínio `scsi.digital`;
- zona DNS administrada no Cloudflare;
- acesso ao Git;
- acesso ao GHCR;
- repositório do projeto;
- credenciais necessárias para produção.

Recomendação mínima operacional:

- 1 VPS para o primeiro ambiente;
- IP público;
- portas 80/443 disponíveis;
- espaço em disco para imagens, volumes e backups.

Para um Swarm multi-node futuro, os nodes também precisarão permitir comunicação nas portas de controle e overlay do Swarm.

---

## 28.2 Acessar a VPS

Do computador local:

```bash
ssh usuario@IP_DA_VPS
```

Confirmar sistema:

```bash
cat /etc/os-release
uname -a
```

Atualizar:

```bash
sudo apt update
sudo apt upgrade -y
```

Instalar ferramentas básicas:

```bash
sudo apt install -y \
  ca-certificates \
  curl \
  git \
  gnupg \
  ufw \
  jq
```

---

# 29. Configuração básica de firewall

Antes de ativar o firewall, confirme que a porta SSH utilizada está liberada.

Exemplo para SSH na porta 22:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

Verificar:

```bash
sudo ufw status verbose
```

## 29.1 Swarm multi-node

Se futuramente houver mais de um node, permitir entre os nodes:

```text
2377/tcp
7946/tcp
7946/udp
4789/udp
```

Não exponha essas portas publicamente sem necessidade. Restrinja-as ao tráfego entre nodes do Swarm.

---

# 30. Instalação do Docker Engine

Utilizar o repositório oficial do Docker.

Adicionar chave:

```bash
sudo apt update
sudo apt install -y ca-certificates curl

sudo install -m 0755 -d /etc/apt/keyrings

sudo curl -fsSL \
  https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc

sudo chmod a+r /etc/apt/keyrings/docker.asc
```

Criar source:

```bash
sudo tee /etc/apt/sources.list.d/docker.sources > /dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
```

Atualizar:

```bash
sudo apt update
```

Instalar:

```bash
sudo apt install -y \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin
```

Verificar:

```bash
sudo systemctl status docker
```

Se necessário:

```bash
sudo systemctl enable docker
sudo systemctl start docker
```

Testar:

```bash
sudo docker run hello-world
```

Opcionalmente adicionar o usuário atual ao grupo Docker:

```bash
sudo usermod -aG docker $USER
```

Depois disso, encerre a sessão SSH e conecte novamente.

Verifique:

```bash
docker version
docker compose version
```

---

# 31. Inicializar Docker Swarm

Verificar estado:

```bash
docker info --format '{{.Swarm.LocalNodeState}}'
```

Inicializar:

```bash
docker swarm init
```

Em VPS com múltiplas interfaces, utilize o IP correto da interface pública/privada:

```bash
docker swarm init --advertise-addr IP_DA_VPS
```

Verificar:

```bash
docker node ls
```

Resultado esperado: o node atual aparece como `Leader`/manager ativo.

O `docker swarm init` cria o Swarm e também configura a rede ingress padrão.

Guardar as informações de join apenas se outros nodes forem adicionados.

---

# 32. Criar redes overlay

## 32.1 Rede pública

Criar:

```bash
docker network create \
  --driver overlay \
  --scope swarm \
  --attachable \
  traefik_public
```

Como a rede é externa ao stack, ela não deve ser criada automaticamente pelo `stack.yml`.

Verificar:

```bash
docker network inspect traefik_public
```

## 32.2 Rede interna

Criar:

```bash
docker network create \
  --driver overlay \
  --scope swarm \
  --internal \
  --attachable \
  scsi_v1_internal
```

Verificar:

```bash
docker network inspect scsi_v1_internal
```

## 32.3 Rede de egress

Criar:

```bash
docker network create \
  --driver overlay \
  --scope swarm \
  --attachable \
  scsi_v1_egress
```

Verificar:

```bash
docker network ls
```

Devem existir:

```text
traefik_public
scsi_v1_internal
scsi_v1_egress
```

---

# 33. Configurar DNS no Cloudflare

Na zona `scsi.digital`, criar/apontar o DNS necessário para a aplicação.

Exemplo:

```text
scsi.digital        A       IP_DA_VPS
*.scsi.digital      A       IP_DA_VPS
```

A configuração final depende de quais subdomínios serão utilizados.

Confirmar propagação:

```bash
dig scsi.digital
dig qualquer-subdominio.scsi.digital
```

---

# 34. Criar API Token do Cloudflare

No Cloudflare:

1. acessar o dashboard;
2. abrir o perfil/API Tokens;
3. criar um novo token;
4. utilizar o template de edição de DNS, quando disponível;
5. limitar o recurso à zona `scsi.digital`;
6. conceder somente a permissão necessária para editar DNS;
7. revisar o token;
8. criar o token;
9. copiar o valor somente no momento da criação;
10. não salvar o token em Git.

O objetivo é limitar o token à zona necessária e à operação DNS necessária para o DNS-01.

---

# 35. Criar Docker Secret do Cloudflare

Não colocar o token diretamente no `stack.yml`.

Criar:

```bash
printf '%s' 'COLE_AQUI_O_TOKEN_CLOUDFLARE' | \
  docker secret create CLOUDFLARE_DNS_API_TOKEN -
```

Verificar:

```bash
docker secret ls
```

Deve aparecer:

```text
CLOUDFLARE_DNS_API_TOKEN
```

Nunca execute:

```bash
echo "TOKEN_REAL"
```

em ambientes onde isso possa ficar registrado em histórico/logs.

---

# 36. Criar demais secrets

Os secrets definitivos dependem dos nomes definidos no stack.

Exemplo conceitual:

```bash
printf '%s' 'SENHA_FORTE_POSTGRES' | \
  docker secret create POSTGRES_PASSWORD -

printf '%s' 'SENHA_FORTE_RABBITMQ' | \
  docker secret create RABBITMQ_PASSWORD -
```

Listar:

```bash
docker secret ls
```

Importante: não crie secrets duplicados com nomes conflitantes.

Se o stack utilizar senha via `.env` em vez de Docker Secret por decisão explícita, a variável deve permanecer em arquivo `.env` gitignored e nunca no repositório.

---

# 37. Preparar diretório da aplicação

Exemplo:

```bash
sudo mkdir -p /opt/scsi_v1
sudo chown -R $USER:$USER /opt/scsi_v1
cd /opt/scsi_v1
```

Clonar:

```bash
git clone URL_DO_REPOSITORIO .
```

Ou, se o projeto já existir:

```bash
git pull
```

Verificar:

```bash
git status
```

---

# 38. Criar `.env` de produção

Criar:

```bash
nano .env
```

Exemplo de estrutura:

```env
DEBUG=False

ALLOWED_HOSTS=scsi.digital,.scsi.digital,localhost,127.0.0.1

CSRF_TRUSTED_ORIGINS=https://scsi.digital,https://*.scsi.digital

DJANGO_SETTINGS_MODULE=core.settings

POSTGRES_DB=scsi
POSTGRES_USER=scsi
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

REDIS_URL=redis://redis:6379/0

CELERY_BROKER_URL=amqp://rabbitmq:5672//

OPENAI_API_KEY=COLOCAR_DE_ACORDO_COM_A_ESTRATEGIA_DE_SECRET_DO_PROJETO
AI_MODEL=gpt-5.5-mini
```

Os nomes definitivos devem corresponder exatamente ao `settings.py` e ao stack.

Proteger:

```bash
chmod 600 .env
```

Verificar que o arquivo está no `.gitignore`:

```bash
grep -n '^\.env$' .gitignore
```

Não versionar o `.env`.

---

# 39. Configuração de proxy no Django

Em produção, o Django deve considerar o header:

```python
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
```

A configuração de redirect HTTPS deve ser compatível com o fato de o TLS terminar no Traefik.

O endpoint `/health/` deve possuir a exceção necessária para funcionar corretamente durante healthchecks internos.

---

# 40. Build e publicação no GHCR

Autenticar no GitHub Container Registry:

```bash
echo "$GHCR_TOKEN" | \
  docker login ghcr.io \
  -u SEU_USUARIO_GITHUB \
  --password-stdin
```

Build:

```bash
docker build \
  -t ghcr.io/pycodebr/scsi_v1:latest \
  .
```

Publicar:

```bash
docker push ghcr.io/pycodebr/scsi_v1:latest
```

Para produção, recomenda-se utilizar tags imutáveis por versão/commit além de `latest`.

Exemplo:

```bash
docker build \
  -t ghcr.io/pycodebr/scsi_v1:2026-09-29 .
```

```bash
docker push ghcr.io/pycodebr/scsi_v1:2026-09-29
```

---

# 41. Stack de produção

O stack deve conter:

- Traefik;
- Django;
- PostgreSQL;
- Redis;
- RabbitMQ;
- Celery Worker;
- Celery Beat.

Cada serviço deve possuir apenas as redes necessárias.

### Matriz de redes

| Serviço | traefik_public | scsi_v1_internal | scsi_v1_egress |
|---|---:|---:|---:|
| Traefik | SIM | NÃO | NÃO |
| Django | SIM | SIM | NÃO |
| PostgreSQL | NÃO | SIM | NÃO |
| Redis | NÃO | SIM | NÃO |
| RabbitMQ | NÃO | SIM | NÃO |
| Celery Worker | NÃO | SIM | SIM |
| Celery Beat | NÃO | SIM | SIM |

---

# 42. Deploy do stack

Antes do deploy:

```bash
docker stack config -c stack.yml
```

Corrigir qualquer erro antes de continuar.

Deploy:

```bash
docker stack deploy \
  --with-registry-auth \
  -c stack.yml \
  scsi_v1
```

Verificar:

```bash
docker stack services scsi_v1
```

Verificar tasks:

```bash
docker stack ps scsi_v1
```

Verificar nodes:

```bash
docker node ls
```

---

# 43. Verificar healthchecks

Ver serviços:

```bash
docker service ls
```

Ver detalhes:

```bash
docker service ps scsi_v1_app
```

Logs:

```bash
docker service logs \
  --tail 200 \
  scsi_v1_app
```

RabbitMQ:

```bash
docker service logs \
  --tail 200 \
  scsi_v1_rabbitmq
```

Celery:

```bash
docker service logs \
  --tail 200 \
  scsi_v1_celery_worker
```

Verificar endpoint:

```bash
curl -i http://127.0.0.1/health/
```

Se o Traefik estiver configurado para TLS:

```bash
curl -I https://scsi.digital/health/
```

---

# 44. Verificar certificado wildcard

O Traefik deve executar o DNS-01 utilizando Cloudflare.

Verificar logs:

```bash
docker service logs \
  --tail 300 \
  scsi_v1_traefik
```

Procurar mensagens relacionadas a:

- ACME;
- DNS challenge;
- certificate;
- lego;
- Cloudflare.

Verificar certificado externo:

```bash
openssl s_client \
  -connect scsi.digital:443 \
  -servername scsi.digital \
  </dev/null 2>/dev/null | \
  openssl x509 -noout -subject -issuer -dates -ext subjectAltName
```

O certificado deve apresentar SANs compatíveis com:

```text
scsi.digital
*.scsi.digital
```

Testar subdomínio:

```bash
curl -I https://subdominio.scsi.digital
```

---

# 45. Verificar renovação

Não aguardar o vencimento para descobrir problemas.

Validar periodicamente:

- logs do Traefik;
- armazenamento ACME;
- validade do certificado;
- funcionamento do DNS challenge.

O arquivo de armazenamento ACME deve permanecer em volume persistente.

---

# 46. Script `scripts/deploy.sh`

O script deve executar:

```text
1. validar ambiente
2. validar Swarm
3. validar networks
4. validar secrets
5. validar DEBUG=False
6. validar ALLOWED_HOSTS
7. git pull
8. build
9. login GHCR quando necessário
10. push
11. docker stack deploy --with-registry-auth
12. force update
13. aguardar rollout
14. verificar health
15. exibir diagnóstico em caso de falha
```

Uso esperado:

```bash
./scripts/deploy.sh
```

Redeploy sem rebuild:

```bash
./scripts/deploy.sh --skip-build
```

O script não deve utilizar:

```bash
source .env
```

Deve utilizar parser seguro.

---

# 47. Estratégia de rollout

O app deve utilizar:

```yaml
update_config:
  order: start-first
  failure_action: rollback
```

Objetivo:

1. iniciar nova réplica;
2. aguardar ficar saudável;
3. somente então remover a antiga;
4. executar rollback caso a nova réplica falhe.

---

# 48. Backup

## PostgreSQL

O backup deve produzir arquivo versionado por data.

Exemplo conceitual:

```bash
docker exec CONTAINER_POSTGRES \
  pg_dump -U USUARIO -d BANCO > backup.sql
```

No Swarm, o procedimento definitivo deve utilizar o serviço/container correto e credenciais protegidas.

## Media

Realizar cópia do volume/media para armazenamento de backup.

## Rotação

Manter política de retenção documentada.

## Restauração

O projeto deve documentar e validar:

```text
backup -> restauração -> validação -> recuperação da aplicação
```

Um backup não deve ser considerado confiável sem um procedimento de restauração verificável.

---

# 49. Checklist pós-deploy

- [ ] `docker node ls` saudável.
- [ ] Todos os serviços em estado esperado.
- [ ] Nenhum serviço em restart loop.
- [ ] Healthchecks passando.
- [ ] PostgreSQL operacional.
- [ ] Redis operacional.
- [ ] RabbitMQ operacional.
- [ ] Celery Worker operacional.
- [ ] Celery Beat operacional.
- [ ] Traefik operacional.
- [ ] `/health/` retornando 200.
- [ ] `https://scsi.digital` funcionando.
- [ ] Certificado TLS válido.
- [ ] Wildcard válido.
- [ ] DNS correto.
- [ ] Login funcionando.
- [ ] Dashboard funcionando.
- [ ] Static files funcionando.
- [ ] Media protegida.
- [ ] Task Celery executando.
- [ ] Notificação funcionando.
- [ ] Backup configurado.
- [ ] Logs acessíveis.
- [ ] Rollback documentado.

---

# 50. Troubleshooting

## 50.1 Serviço reiniciando

```bash
docker service ps scsi_v1_NOME_DO_SERVICO --no-trunc
```

Depois:

```bash
docker service logs --tail 300 scsi_v1_NOME_DO_SERVICO
```

Verificar:

- healthcheck;
- variável ausente;
- secret ausente;
- dependência;
- migration;
- conexão;
- memória.

## 50.2 PostgreSQL não inicia

Verificar:

```bash
docker service logs --tail 300 scsi_v1_postgres
```

Confirmar volume e credenciais.

## 50.3 Celery não conecta

Verificar:

```bash
docker service logs --tail 300 scsi_v1_celery_worker
```

Confirmar:

- RabbitMQ;
- DNS interno;
- URL do broker;
- rede `scsi_v1_internal`.

## 50.4 Celery não acessa OpenAI

Confirmar:

- `scsi_v1_egress`;
- DNS;
- acesso externo;
- credencial da OpenAI;
- configuração do serviço.

Não conectar Celery à `traefik_public` para resolver esse problema.

## 50.5 Certificado não emitido

Verificar:

```bash
docker service logs --tail 500 scsi_v1_traefik
```

Confirmar:

- secret Cloudflare;
- `CF_DNS_API_TOKEN_FILE`;
- zona correta;
- permissão DNS;
- domínio;
- resolver ACME;
- DNS challenge;
- persistência do armazenamento ACME.

## 50.6 Aplicação retorna 400

Verificar:

```text
ALLOWED_HOSTS
CSRF_TRUSTED_ORIGINS
```

Confirmar:

```env
ALLOWED_HOSTS=scsi.digital,.scsi.digital,localhost,127.0.0.1
```

e:

```env
CSRF_TRUSTED_ORIGINS=https://scsi.digital,https://*.scsi.digital
```

## 50.7 Redirect HTTPS infinito

Verificar:

```python
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
```

e a configuração de headers/redirect do Traefik.

## 50.8 Static files ausentes

Verificar:

```bash
collectstatic --clear
```

e o volume/configuração de staticfiles.

## 50.9 Migration falhando em múltiplas réplicas

Confirmar que o entrypoint usa advisory lock PostgreSQL.

Não executar migrations concorrentes em múltiplas réplicas.

---

# 51. Critérios de aceite do MVP

O MVP somente deve ser considerado concluído quando:

- [ ] autenticação funciona;
- [ ] permissões funcionam;
- [ ] clientes podem ser gerenciados;
- [ ] múltiplos cachorros podem ser vinculados;
- [ ] programação pode ser cadastrada;
- [ ] passeios são gerados;
- [ ] passeios podem ser visualizados;
- [ ] passeios podem ser marcados como realizados;
- [ ] passeios podem ser cancelados;
- [ ] passeios podem ser marcados como não realizados;
- [ ] histórico funciona;
- [ ] filtros funcionam;
- [ ] controle mensal funciona;
- [ ] dashboard funciona;
- [ ] dados não vazam entre escopos;
- [ ] aplicação é responsiva;
- [ ] background tasks não bloqueiam a UI;
- [ ] Docker local funciona;
- [ ] Swarm funciona;
- [ ] healthchecks funcionam;
- [ ] TLS funciona;
- [ ] wildcard é emitido;
- [ ] backup está documentado;
- [ ] deploy automatizado funciona;
- [ ] rollback está documentado;
- [ ] documentação está atualizada.

---

# 52. Definition of Done

Uma tarefa somente pode ser considerada concluída quando:

- [ ] requisito implementado;
- [ ] código em inglês;
- [ ] interface em português brasileiro;
- [ ] PEP 8 respeitado;
- [ ] segurança considerada;
- [ ] permissões consideradas;
- [ ] queries revisadas;
- [ ] migrations criadas quando necessárias;
- [ ] documentação atualizada quando necessário;
- [ ] Django checks executados;
- [ ] comportamento esperado verificado;
- [ ] nenhum secret exposto;
- [ ] nenhum arquivo não relacionado alterado sem necessidade.

---

# 53. Decisões em aberto

Os pontos abaixo devem ser decididos antes da implementação definitiva do domínio correspondente.

- [x] Campos completos de `Client`.
- [x] Campos completos de `Dog`.
- [x] Campos completos de `Walk`.
- [x] Estados definitivos de `Walk`.
- [ ] Regras de cancelamento.
- [ ] Regras financeiras de cancelamento.
- [x] Regra exata para "passeios restantes". — Sprint 9: `contratados − realizados − cancelados − não realizados` (nunca negativo; saldo operacional, sem impacto financeiro); ver RF-011. — 26/10/2026: `contratados` passou a refletir o **pacote mensal por quantidade** (`Dog.monthly_walks_quota`) quando preenchido, substituindo a derivação por calendário; ver RF-011.
- [x] Modelo definitivo de recorrência.
- [x] Janela de geração de passeios.
- [x] Comportamento quando uma programação é alterada. — 26/10/2026: o resync passou a gerar desde o início da programação ativa mais antiga do cachorro — cadastros retroativos geram seus passeios passados contratados como `previsto` (a janela padrão de 7 dias não os alcançaria) — mantendo o resync dos futuros e a preservação de desfechos; ver RF-005.
- [ ] Regras de feriados.
- [ ] Regras de remarcação.
- [x] Modelo de notificações. — Sprint 11: in-app por usuário (nível/título/mensagem/link/lida); ver seção 9.1 e docs/celery.md.
- [x] Casos de uso de IA do MVP. — Sprint 12: **resumo operacional mensal** (contadores de RF-011 + observações do mês, por mês e opcionalmente por cliente); ver seção 19 e docs/ia.md.
- [ ] Política definitiva de armazenamento de media em ambiente multi-node.
- [ ] Política de retenção de backups.
- [ ] Política de retenção de logs.
- [ ] Estratégia de tags imutáveis das imagens.
- [ ] Estratégia futura para múltiplos nodes do Swarm.

---

# 54. Referências técnicas

As instruções de infraestrutura deste documento devem ser confrontadas com a documentação oficial vigente durante a implementação.

- Docker Engine — instalação no Ubuntu: https://docs.docker.com/engine/install/ubuntu/
- Docker Swarm — `docker swarm init`: https://docs.docker.com/reference/cli/docker/swarm/init/
- Docker Overlay Networks: https://docs.docker.com/engine/network/drivers/overlay/
- Docker Swarm networking: https://docs.docker.com/engine/swarm/networking/
- Cloudflare — criação de API Tokens: https://developers.cloudflare.com/fundamentals/api/get-started/create-token/
- Cloudflare — templates de API Tokens: https://developers.cloudflare.com/fundamentals/api/reference/template/
- Traefik — DNS Challenge/Let's Encrypt: https://doc.traefik.io/traefik/v3.0/user-guides/docker-compose/acme-dns/

---

# 55. Nota de manutenção do PRD

Este documento é vivo.

Sempre que uma decisão arquitetural ou funcional relevante for tomada:

1. atualizar este PRD;
2. atualizar a documentação técnica;
3. atualizar as sprints/checklists;
4. registrar impacto;
5. evitar que o código se torne a única fonte de verdade.

O PRD deve permanecer sincronizado com a implementação real do sistema.
