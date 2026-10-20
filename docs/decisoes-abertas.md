# Decisões abertas

**Data do registro:** 2026-10-20 (Sprint 0)
**Fonte:** [PRD](./PRD.md) seção 53.

Regras (PRD seção 1.1):

1. Nenhuma regra de negócio não especificada deve ser inventada durante a
   implementação.
2. Quando houver dúvida sobre um requisito ainda não decidido, o ponto é
   registrado aqui como **Open Decision**.
3. Decisões aprovadas devem ser registradas no PRD e aqui (movendo para
   "Resolvidas") antes de serem consideradas parte da arquitetura oficial.

| # | Decisão | Domínio | Sprint de resolução | Status |
|---|---|---|---|---|
| 1 | Campos completos de `Client` | clients | 4 | Aberta |
| 2 | Campos completos de `Dog` | dogs | 5 | Aberta |
| 3 | Campos completos de `Walk` | walks | 7 | Aberta |
| 4 | Estados definitivos de `Walk` | walks | 7 | Aberta |
| 5 | Regras de cancelamento | walks | 8 | Aberta |
| 6 | Regras financeiras de cancelamento | walks/business | 8 | Aberta |
| 7 | Regra exata para "passeios restantes" | controle mensal | 9 | Aberta |
| 8 | Modelo definitivo de recorrência | scheduling | 6 | Aberta |
| 9 | Janela de geração de passeios | scheduling/walks | 7 | Aberta |
| 10 | Comportamento quando uma programação é alterada | scheduling/walks | 7 | Aberta |
| 11 | Regras de feriados | scheduling/walks | 7 | Aberta |
| 12 | Regras de remarcação | walks | 8 | Aberta |
| 13 | Modelo de notificações | notifications | 11 | Aberta |
| 14 | Casos de uso de IA do MVP | ai | 12 | Aberta |
| 15 | Política definitiva de armazenamento de media em ambiente multi-node | infra | 17+ | Aberta |
| 16 | Política de retenção de backups | infra | 21 | Aberta |
| 17 | Política de retenção de logs | infra | 22+ | Aberta |
| 18 | Estratégia de tags imutáveis das imagens | infra/CI | 18 | Aberta |
| 19 | Estratégia futura para múltiplos nodes do Swarm | infra | Pós-MVP | Aberta |

## Resolvidas

(nenhuma até o momento)

## Como resolver uma decisão aberta

1. Levantar o ponto com o responsável pelo projeto.
2. Registrar a decisão aprovada no PRD (seção correspondente).
3. Atualizar esta tabela movendo o item para "Resolvidas" com data e referência.
4. Quando aplicável, registrar um ADR em [adr/](./adr/).
