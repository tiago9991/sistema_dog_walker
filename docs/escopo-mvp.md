# Escopo do MVP

**Data:** 2026-10-20 (Sprint 0)
**Fonte:** [PRD](./PRD.md) seções 2, 3, 51 e 53.

## Objetivo do MVP

Sistema web operacional para um Dog Walker individual, permitindo controlar
clientes, cachorros, programação, geração e execução de passeios, histórico,
controle mensal e dashboard — com infraestrutura Docker/Swarm pronta para
produção em `scsi.digital`.

## Dentro do escopo (MVP)

### Funcional

1. **Usuários e permissões** (RF-001): login/logout, usuários Django, grupos,
   permissões nativas verificadas no backend.
2. **Clientes** (RF-002): CRUD, pesquisa, desativação preservando histórico.
3. **Cachorros** (RF-003): CRUD vinculado a cliente, múltiplos por cliente,
   desativação, histórico.
4. **Programação** (RF-004): frequência, dias da semana, período de validade.
5. **Geração de passeios** (RF-005): determinística, idempotente, timezone
   `America/Sao_Paulo`.
6. **Operação dos passeios** (RF-006/007/008): visões diária/semanal/mensal,
   ações realizado/cancelado/não realizado, observações.
7. **Histórico** (RF-009) e **filtros** (RF-012).
8. **Controle mensal** (RF-011): contratados, previstos, realizados,
   cancelados, não realizados, restantes.
9. **Dashboard** (RF-010): indicadores operacionais.
10. **Notificações e background** (RNF-004): Celery + RabbitMQ + Redis com
    feedback na interface.
11. **IA**: base arquitetural (OpenAI + LangChain/LangGraph) com primeiro caso
    de uso a definir (decisão aberta).
12. **Relatórios**: primeiro relatório com ReportLab/PyPDF.
13. **Dados de demonstração**: management command com dados fictícios.

### Técnico / Infraestrutura

- PostgreSQL, Redis, RabbitMQ via Docker Compose local.
- Produção em Docker Swarm (single-node) com Traefik, TLS Let's Encrypt
  wildcard via DNS-01 Cloudflare.
- Healthchecks para todos os serviços.
- Imagem publicada no GHCR (`ghcr.io/pycodebr/scsi_v1`).
- Deploy automatizado (`scripts/deploy.sh`) e backup (`scripts/backup.sh`).
- Documentação (MkDocs) e design system aplicado à interface.

## Fora do escopo do MVP

Conforme PRD seção 3.2:

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

Esses itens podem ser registrados como evolução futura. A estratégia futura
para múltiplos nodes do Swarm e a política de armazenamento de media
multi-node permanecem como decisões abertas.

## Critérios de aceite do MVP

O MVP somente será considerado concluído quando todos os critérios da seção 51
do PRD estiverem satisfeitos. O checklist completo está no PRD.

## Regras de execução

- Desenvolvimento em pequenos incrementos (PRD seção 26).
- Tarefa concluída somente atende à Definition of Done (PRD seção 52).
- Requisito não decidido é registrado como decisão aberta — nunca inventado.
- Interface em português brasileiro; código em inglês; PEP 8.
