# ADR-0001 — Apps Django por domínio

- **Status:** Aceito
- **Data:** 2026-10-20 (Sprint 0)
- **Contexto:** PRD seção 8

## Decisão

O projeto Django principal se chama `core`. Existe um app `base` para recursos
compartilhados. Cada domínio de negócio será um app Django independente
(`clients`, `dogs`, `walks`, `scheduling`, `dashboard`, `notifications`,
`ai`, `reports`).

## Motivação

- Separação de responsabilidades por domínio.
- Permissões, URLs, admin e testes organizados por área de negócio.
- Evita um app monolítico e permite evolução incremental.

## Restrições

- Apps são criados somente quando o domínio demonstrar necessidade real
  (conforme o sprint correspondente), nunca artificialmente para cumprir uma
  lista.
- Recursos compartilhados ficam em `base`, não duplicados entre domínios.

## Consequências

- Em Sprint 0 apenas `base` foi criado (vazio, registrado em `INSTALLED_APPS`).
- Demais apps surgem nas Sprints 4–13.
