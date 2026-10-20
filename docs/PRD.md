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

Grupos (criados pela migration `base.0001_groups`):

| Grupo | Permissões |
|---|---|
| `Operação` | `view`/`add`/`change` de `Client` e `Dog` |
| `Leitura` | `view` de `Client` e `Dog` |

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

Campos de negócio definitivos (definidos na Sprint 5 — decisão 2 da seção 53 resolvida):

| Campo | Tipo | Observação |
|---|---|---|
| `name` | `CharField(150)` | obrigatório |
| `breed` | `CharField(100)` | opcional |
| `notes` | `TextField` | opcional |
| `is_active` | `BooleanField` | desativação soft; histórico preservado |
| `deactivated_at` | `DateTimeField` | preenchido na desativação |

Campos técnicos:

- `created_at`
- `updated_at`

### WalkSchedule

Representa a programação recorrente.

Deve possuir vínculo com cachorro e informações necessárias para gerar passeios.

### Walk

Representa um passeio previsto/realizado/cancelado.

Deve possuir:

- cachorro;
- data/hora ou data operacional conforme regra aprovada;
- status;
- observação;
- timestamps.

### Notification

Representa notificações para o usuário quando necessário.

### AI Task / AI Analysis

A persistência definitiva de resultados de IA deve ser definida quando os casos de uso de IA forem implementados.

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

- [ ] Definir modelo definitivo de programação.
- [ ] Definir frequência.
- [ ] Definir dias da semana.
- [ ] Definir período de validade.
- [ ] Criar model de programação.
- [ ] Criar migration.
- [ ] Criar CRUD.
- [ ] Criar validações.
- [ ] Documentar regras de recorrência.

## Sprint 7 — Geração de passeios

- [ ] Definir algoritmo de geração.
- [ ] Definir janela de geração.
- [ ] Definir comportamento em alterações de programação.
- [ ] Criar model Walk.
- [ ] Criar statuses.
- [ ] Criar constraints contra duplicidade.
- [ ] Implementar geração.
- [ ] Validar timezone.
- [ ] Criar command de geração.
- [ ] Criar task Celery quando necessário.
- [ ] Validar idempotência.

## Sprint 8 — Operação dos passeios

- [ ] Criar listagem diária.
- [ ] Criar visão semanal.
- [ ] Criar visão mensal.
- [ ] Criar filtro por cliente.
- [ ] Criar filtro por cachorro.
- [ ] Criar filtro por data.
- [ ] Criar filtro por mês.
- [ ] Criar filtro por status.
- [ ] Criar ação realizado.
- [ ] Criar ação cancelado.
- [ ] Criar ação não realizado.
- [ ] Criar observações.
- [ ] Criar histórico.

## Sprint 9 — Controle mensal

- [ ] Definir regra de cálculo.
- [ ] Implementar passeios contratados.
- [ ] Implementar previstos.
- [ ] Implementar realizados.
- [ ] Implementar cancelados.
- [ ] Implementar não realizados.
- [ ] Implementar restantes.
- [ ] Criar visão por cliente.
- [ ] Criar visão por cachorro.
- [ ] Validar cálculos com dados fake.

## Sprint 10 — Dashboard

- [ ] Definir indicadores.
- [ ] Criar consultas agregadas.
- [ ] Otimizar queries.
- [ ] Criar cards.
- [ ] Criar visão de passeios.
- [ ] Criar visão mensal.
- [ ] Criar filtros relevantes.
- [ ] Aplicar design system.
- [ ] Validar responsividade.

## Sprint 11 — Notificações e background

- [ ] Configurar Celery.
- [ ] Configurar RabbitMQ.
- [ ] Configurar Redis.
- [ ] Configurar Worker.
- [ ] Configurar Beat.
- [ ] Configurar `dj-celery-panel`.
- [ ] Criar modelo de notificação.
- [ ] Criar feedback de loading.
- [ ] Criar conclusão de task.
- [ ] Criar notificação na interface.
- [ ] Validar que requests não ficam bloqueados.

## Sprint 12 — IA

- [ ] Configurar OpenAI.
- [ ] Configurar LangChain.
- [ ] Configurar LangGraph.
- [ ] Configurar GPT-5.5-mini.
- [ ] Criar abstração inicial de IA.
- [ ] Definir primeiro caso de uso.
- [ ] Criar prompt especializado.
- [ ] Criar workflow LangGraph quando necessário.
- [ ] Criar task Celery.
- [ ] Persistir resultado quando necessário.
- [ ] Criar notificação de conclusão.
- [ ] Documentar arquitetura de IA.

## Sprint 13 — Relatórios

- [ ] Configurar ReportLab.
- [ ] Configurar PyPDF.
- [ ] Criar primeiro relatório.
- [ ] Criar layout.
- [ ] Validar português.
- [ ] Validar timezone.
- [ ] Implementar geração assíncrona se necessário.
- [ ] Documentar relatórios.

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
- [ ] Campos completos de `Walk`.
- [ ] Estados definitivos de `Walk`.
- [ ] Regras de cancelamento.
- [ ] Regras financeiras de cancelamento.
- [ ] Regra exata para "passeios restantes".
- [ ] Modelo definitivo de recorrência.
- [ ] Janela de geração de passeios.
- [ ] Comportamento quando uma programação é alterada.
- [ ] Regras de feriados.
- [ ] Regras de remarcação.
- [ ] Modelo de notificações.
- [ ] Casos de uso de IA do MVP.
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
