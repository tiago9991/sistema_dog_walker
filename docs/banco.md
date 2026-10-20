# Banco de dados (PostgreSQL)

Documentação operacional do banco de dados implementada na **Sprint 1**. A fonte
de verdade funcional é o [PRD](./PRD.md) (seções 9, 10, 16 e 17); este documento
cobre a configuração concreta em vigor.

## Stack

| Camada | Valor |
|---|---|
| SGBD | PostgreSQL 17 (local: container Docker `scsi_pg`, imagem `postgres:17-alpine`) |
| Driver | `psycopg` 3 (`psycopg` + `psycopg-binary` no `requirements.txt`) |
| Configuração | `dj-database-url` + `python-decouple` |

## Conexão (`.env`)

`DATABASE_URL` é resolvida nesta ordem (ver `core/settings.py`):

1. variável de ambiente do processo (produção: Compose/Swarm);
2. arquivo `.env` (desenvolvimento local — não versionado);
3. vazia → fallback para SQLite (`db.sqlite3`), apenas para execuções rápidas
   sem uma instância PostgreSQL.

`.env` local de desenvolvimento:

```env
DATABASE_URL=postgres://scsi:scsi@127.0.0.1:5432/scsi
```

Dentro do Compose, o serviço `django` recebe `DATABASE_URL` apontando para
o host `postgres` (nome do serviço), sobrescrevendo o valor do `.env`.

Ajustes aplicados às conexões no `settings.py`:

- `CONN_MAX_AGE = 60` — conexões persistentes;
- `CONN_HEALTH_CHECKS = True` — evita usar uma conexão morta (por exemplo,
  após um restart do container);
- `connect_timeout = 5` (PostgreSQL) — falha rápido em vez de travar para
  sempre quando o banco está inacessível.

> Pitfall corrigido na Sprint 1: `dj_database_url.config()` lê a variável de
> ambiente do processo, **não** o `.env`. Por isso a URL agora é lida com
> `python-decouple` (que resolve env do processo e `.env`) e repassada para
> `dj_database_url.parse()`. Sem isso, o Django cai silenciosamente no SQLite.

## PostgreSQL local (Docker Compose)

O PostgreSQL é o serviço `postgres` do `compose.yml` (imagem
`postgres:17-alpine`, credenciais `scsi:scsi`, publicado em `127.0.0.1:5432`
para uso a partir do host). O container avulso `scsi_pg` da Sprint 1 foi
substituído pelo serviço; os dados foram preservados no volume
`scsi_pg_data`, declarado `external` no Compose para que
`docker compose down -v` nunca o remova.

```powershell
docker compose up -d            # sobe tudo (banco incluso)
docker compose up -d postgres   # apenas o banco
```

- Healthcheck conforme PRD §16 (`pg_isready`).
- Primeira execução em máquina nova: `docker volume create scsi_pg_data`
  antes do `up` (volume externo não é criado pelo Compose).

## Modelo base

`base.models.BaseModel` (abstrata) — timestamps obrigatórios do PRD §9.1:

| Campo | Comportamento |
|---|---|
| `created_at` | `auto_now_add` |
| `updated_at` | `auto_now` |

Modelos de negócio (`Client`, `Dog`, `Walk`, ...) devem herdar de `BaseModel`
em vez de declarar os timestamps. Sendo abstrata, não gera migration nem tabela
própria.

## Estratégia de migrations

1. Migrations por app; **uma migration por mudança lógica** (não agrupar
   mudanças não relacionadas).
2. Nomes descritivos com `--name` (ex.: `makemigrations clients --name create_client`).
3. **Nunca editar migration já aplicada** — conferir com
   `python manage.py showmigrations`; mudança nova = migration nova.
4. Detectar migration esquecida antes de commit/deploy:
   `python manage.py makemigrations --check --dry-run`.
5. Em produção, as migrations rodam no entrypoint com advisory lock PostgreSQL
   (PRD §17) — implementação nas sprints de infraestrutura (2 e 17).
6. A geração de passeios deve ser **idempotente** (PRD §10): repetir o processo
   não cria duplicatas.

## Django Admin

- Disponível em `/admin/`; superusuário local criado com
  `python manage.py createsuperuser` (credenciais ficam com o operador — não
  versionadas).
- "Chrome" do admin (cabeçalho/título em pt-br) configurado em `base/admin.py`.
- Grupos e permissões: nativos do Django (PRD §4) — modelagem na Sprint 3.

## Validação executada (Sprint 1)

- `python manage.py check` — sem issues.
- `python manage.py migrate` — migrations de sistema aplicadas no PostgreSQL
  (`admin`, `auth`, `contenttypes`, `sessions`).
- `python manage.py makemigrations --check --dry-run` — sem drift.
- Query real via `psycopg`: engine `django.db.backends.postgresql`,
  PostgreSQL 17.10, 10 tabelas no schema `public`, `auth_user` com 1 registro.

## Validação executada (Sprint 2 — Compose)

- `docker compose up -d --build` — build da imagem `scsi-django` e pull de
  `redis:8-alpine` e `rabbitmq:4-alpine`.
- `docker compose ps` — `django`, `postgres`, `redis` e `rabbitmq` healthy.
- Entrypoint (PRD §17) no log do `django`: banco OK → migrations
  ("No migrations to apply." — volume `scsi_pg_data` adotado, dados da
  Sprint 1 preservados) → `collectstatic --clear` → `runserver` com
  StatReloader.
- `GET /health/` → 200 `{"status": "ok"}`; `GET /admin/login/` → 200.
- Query real via `psycopg` a partir do host: engine
  `django.db.backends.postgresql`, PostgreSQL 17.10, 10 tabelas no schema
  `public`, `auth_user` com 1 registro (superusuário preservado).

## Reset do ambiente local

```powershell
docker compose down               # containers e rede fora (volumes intactos)
docker volume rm scsi_pg_data     # apaga o banco (destrutivo!)
docker volume create scsi_pg_data
docker compose up -d             # entrypoint roda as migrations sozinho
docker compose exec django python manage.py createsuperuser
```
