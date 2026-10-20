# ADR-0002 — Configuração por variáveis de ambiente

- **Status:** Aceito
- **Data:** 2026-10-20 (Sprint 0)
- **Contexto:** PRD seções 14, 38 e 52 (nenhum secret exposto)

## Decisão

Todo parâmetro que varia entre ambientes é lido do ambiente com
`python-decouple` (`config`):

```python
SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='', cast=Csv())
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='', cast=Csv())
LANGUAGE_CODE = config('LANGUAGE_CODE', default='pt-br')
TIME_ZONE = config('TIME_ZONE', default='America/Sao_Paulo')
```

O banco é configurado com `dj-database-url` a partir de `DATABASE_URL`
(ADR-0005). O arquivo `.env` local é gitignored; `.env.example` versionado
documenta as chaves sem valores sensíveis.

## Motivação

- Sem secrets no repositório (PRD seção 52).
- Configuração idêntica entre local, Compose e Swarm (PRD seção 38).
- Padrão 12-factor.

## Consequências

- `SECRET_KEY` é obrigatória: ambientes sem `.env` falham explicitamente —
  comportamento desejado; não existe fallback inseguro hardcoded.
- `DEBUG` padrão é `False` (fail-safe): o valor `True` precisa ser explícito.
- Valores sensíveis adicionais (senhas PostgreSQL/RabbitMQ, tokens) podem
  migrar para Docker Secrets na produção (PRD seção 15).
