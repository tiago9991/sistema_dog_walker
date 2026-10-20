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
DATABASE_URL=postgres://scsi:scsi@localhost:5432/scsi
```

Ajustes aplicados às conexões no `settings.py`:

- `CONN_MAX_AGE = 60` — conexões persistentes;
- `CONN_HEALTH_CHECKS = True` — evita usar uma conexão morta (por exemplo,
  após um restart do container).

> Pitfall corrigido na Sprint 1: `dj_database_url.config()` lê a variável de
> ambiente do processo, **não** o `.env`. Por isso a URL agora é lida com
> `python-decouple` (que resolve env do processo e `.env`) e repassada para
> `dj_database_url.parse()`. Sem isso, o Django cai silenciosamente no SQLite.

## PostgreSQL local (Docker)

Container de desenvolvimento (a definição formal do Compose é a Sprint 2):

```powershell
docker run -d --name scsi_pg `
  -e POSTGRES_USER=scsi -e POSTGRES_PASSWORD=scsi -e POSTGRES_DB=scsi `
  -p 5432:5432 `
  -v scsi_pg_data:/var/lib/postgresql/data `
  --health-cmd "pg_isready -U scsi -d scsi" `
  --health-interval 5s --health-timeout 3s --health-retries 10 `
  --restart unless-stopped `
  postgres:17-alpine
```

- Dados persistem no volume nomeado `scsi_pg_data`.
- Healthcheck conforme PRD §16 (`pg_isready`).
- Credenciais `scsi:scsi` são exclusivas do desenvolvimento local.

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

## Reset do ambiente local

```powershell
docker rm -f scsi_pg
docker volume rm scsi_pg_data
# recriar o container (comando acima), então:
python manage.py migrate
python manage.py createsuperuser
```
