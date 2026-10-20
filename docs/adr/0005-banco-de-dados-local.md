# ADR-0005 — Banco de dados local e via DATABASE_URL

- **Status:** Aceito
- **Data:** 2026-10-20 (Sprint 0)
- **Contexto:** PRD seções 7, 9 e 14; Sprints 1–2

## Decisão

A configuração de banco é centralizada em `DATABASE_URL` via
`dj-database-url`, com fallback local para SQLite:

```python
DATABASES = {
    'default': dj_database_url.config(
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}',
        conn_max_age=60,
    ),
}
```

- **Desenvolvimento sem `DATABASE_URL`:** SQLite (`db.sqlite3`, gitignored).
- **Desenvolvimento com PostgreSQL local / Docker / produção:** definir
  `DATABASE_URL=postgres://...` (Sprint 1 configura o PostgreSQL local e a
  validação da conexão; produção usa PostgreSQL obrigatoriamente).

## Motivação

- `dj-database-url` já faz parte do `requirements.txt` e unifica a
  configuração entre local, Compose e Swarm.
- Permite rodar checagens da Sprint 0 sem depender de serviço externo.

## Restrições

- SQLite é apenas para conveniência local inicial; o alvo do PRD é
  PostgreSQL (constraints, índices e advisory lock de migrations assumem
  PostgreSQL em produção).
- A estratégia de migrations em múltiplas réplicas (advisory lock) será
  implementada no entrypoint (PRD seção 17, Sprints 2/17).

## Consequências

- Nenhuma configuração adicional por ambiente além de `DATABASE_URL`.
- Migrations devem ser compatíveis com PostgreSQL desde o início.
