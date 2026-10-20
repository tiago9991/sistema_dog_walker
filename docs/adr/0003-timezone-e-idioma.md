# ADR-0003 — Timezone America/Sao_Paulo e idioma pt-br

- **Status:** Aceito
- **Data:** 2026-10-20 (Sprint 0)
- **Contexto:** PRD cabeçalho e seções 5 (RF-005), 8

## Decisão

```python
LANGUAGE_CODE = config('LANGUAGE_CODE', default='pt-br')
TIME_ZONE = config('TIME_ZONE', default='America/Sao_Paulo')
USE_I18N = True
USE_TZ = True
```

- Timezone padrão da aplicação: `America/Sao_Paulo`.
- Idioma da interface: português brasileiro.
- `USE_TZ = True` mantido: datas são persistidas em UTC e convertidas para
  `America/Sao_Paulo` na apresentação, conforme exigência do Django com
  timezone-aware datetimes.

## Motivação

- Exigência explícita do PRD (RF-005: utilizar timezone `America/Sao_Paulo`).
- Interface em pt-br é requisito de produto; código permanece em inglês.

## Consequências

- Toda geração/consulta de passeios deve usar timezone-aware datetimes
  (`zoneinfo`/`django.utils.timezone`), sem datas naive — a validação da
  timezone ocorre na Sprint 7.
- Valores podem ser sobrescritos por ambiente, mas o padrão já é o exigido
  pelo PRD.
