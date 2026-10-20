# Requisitos — Baseline confirmada

**Data de confirmação:** 2026-10-20 (Sprint 0)
**Fonte:** [PRD](./PRD.md) seções 5 e 6.

Os requisitos abaixo foram revisados e confirmados como baseline para
desenvolvimento. Alterações futuras devem seguir a regra de precedência do
PRD (seção 1.1): registrar a decisão no PRD antes de considerá-la oficial.

## Requisitos funcionais

| ID | Requisito | Resumo | Sprint |
|---|---|---|---|
| RF-001 | Gestão de usuários | Cadastro, autenticação, login/logout, permissões, administração | 3 |
| RF-002 | Gestão de clientes | CRUD, pesquisa, desativação preservando histórico | 4 |
| RF-003 | Gestão de cachorros | CRUD por cliente, múltiplos cachorros, desativação, histórico | 5 |
| RF-004 | Programação de passeios | Frequência, dias da semana, período, status | 6 |
| RF-005 | Geração de passeios | Geração determinística e idempotente a partir da programação | 7 |
| RF-006 | Controle de passeios | Visões por dia/semana/mês com status operacional | 8 |
| RF-007 | Confirmação de passeio | Marcar como realizado com registro persistente | 8 |
| RF-008 | Cancelamento e não realização | Registro com observação/motivo quando aplicável | 8 |
| RF-009 | Histórico | Consulta por cachorro: data, status, cliente, observações | 8 |
| RF-010 | Dashboard | Resumo operacional com indicadores mínimos | 10 |
| RF-011 | Controle mensal | Por cliente/cachorro: contratados, previstos, realizados, cancelados, não realizados, restantes | 9 |
| RF-012 | Filtros | Por cliente, cachorro, data, mês e status (backend) | 8 |
| RF-013 | Observações | Observações vinculadas a passeio com controle de acesso | 8 |

Pontos que exigem decisão de negócio antes da implementação final estão
registrados em [decisões abertas](./decisoes-abertas.md). Nenhuma regra não
especificada deve ser inventada durante a implementação.

## Requisitos não funcionais

| ID | Requisito | Resumo |
|---|---|---|
| RNF-001 | Responsividade | Desktop, notebook, tablet e celular |
| RNF-002 | Segurança | Rotas protegidas, autenticação/autorização, anti-acesso horizontal, CSRF, sessões seguras, sem exposição de secrets, HTTPS em produção |
| RNF-003 | Performance | Sem N+1; `select_related`/`prefetch_related`, agregações, índices, paginação, cache e Celery quando apropriado |
| RNF-004 | Assincronicidade | Processamentos demorados via Celery com feedback de loading e notificação de conclusão |
| RNF-005 | Resiliência | Restart policies, healthchecks, resource limits/reservations, rollout `start-first` com rollback automático |

## Observações de confirmação

- Estados mínimos de `Walk` (previsto, realizado, cancelado, não realizado)
  foram confirmados como **mínimos**; a máquina de estados definitiva deve ser
  documentada na Sprint 7 (decisão aberta).
- "Passeios restantes" no controle mensal depende de regra de negócio a aprovar
  (RF-011 / decisão aberta).
- As regras de impacto financeiro de cancelamento estão fora do MVP por falta
  de especificação (decisão aberta).
