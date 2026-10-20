# Sistema de Gestão para Dog Walker Inteligente

Documentação técnica do projeto. A fonte de verdade funcional é o [PRD](./PRD.md).

## Documentos

| Documento | Descrição |
|---|---|
| [PRD](./PRD.md) | Requisitos funcionais, não funcionais, arquitetura, sprints e runbook de deploy |
| [Requisitos](./requisitos.md) | Baseline confirmada de requisitos funcionais e não funcionais |
| [Escopo do MVP](./escopo-mvp.md) | Definição de escopo dentro/fora do MVP |
| [Arquitetura](./arquitetura.md) | Stack, estrutura Django, infraestrutura e design system |
| [Decisões abertas](./decisoes-abertas.md) | Registro de decisões pendentes antes da implementação de cada domínio |
| [ADRs](./adr/) | Registros de decisões arquiteturais |

## Visão geral

Aplicação web para gestão operacional de um trabalho de Dog Walker: clientes,
cachorros, programação de passeios, geração determinística de passeios,
execução, histórico, controle mensal, dashboard, tarefas assíncronas e
funcionalidades de IA.

- **Interface:** Português brasileiro
- **Código:** Inglês
- **Timezone:** `America/Sao_Paulo`
- **Stack:** Python 3.14 / Django 6.1 / PostgreSQL / Celery / RabbitMQ / Redis
- **Infraestrutura:** Docker (Compose local, Swarm em produção), Traefik, GHCR
- **Design system:** `design_system/design-system.html` (referência visual oficial)

## Desenvolvimento local

```bash
# ambiente virtual (já criado em .venv)
.venv\Scripts\activate

# configurar variáveis de ambiente
copy .env.example .env

# verificar configuração
python manage.py check

# servidor de desenvolvimento
python manage.py runserver
```

## Estado atual (Sprint 0 concluída)

- Projeto Django `core` criado e configurado (timezone, idioma, env vars)
- App `base` criado e registrado
- Requisitos confirmados como baseline
- Escopo do MVP definido
- Decisões abertas registradas
- Decisões arquiteturais iniciais registradas (ADRs 0001–0005)
- Repositório Git inicializado
