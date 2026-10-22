# Relatórios — PDF

Implementado na **Sprint 13** (PRD seção 21). Fonte de verdade
funcional: [PRD](./PRD.md).

## Stack

| Camada | Valor |
|---|---|
| Geração | ReportLab 5.1 (`reportlab`) |
| Validação/inspeção | PyPDF 6.21 (`pypdf`) |
| Dados | `walks.services.monthly_control` (RF-011, reusado) |
| Rota | `GET /reports/controle-mensal/` (`reports:monthly_control_pdf`) |
| Permissão | `walks.view_walk` (a mesma da página que o relatório espelha) |

## Primeiro relatório — Controle mensal (PDF)

O **controle mensal em PDF** espelha a página `/walks/controle/`: os
mesmos contadores RF-011 (contratados/previstos/realizados/cancelados/
não realizados/restantes + % de realização), calculados pelo mesmo
serviço — o PDF nunca diverge da tela. Filtros idênticos ao da página:
`?month=YYYY-MM` (padrão: mês corrente), `?client=` e `?dog=`.

Ponto de entrada: botão **"Baixar PDF"** no cabeçalho do controle
mensal (respeita os filtros ativos da página).

## Layout

- **A4 paisagem** (a tabela tem nove colunas) com margens de 12 mm;
- cabeçalho: título, período (nome do mês em pt-br, `date_format 'F Y'`
  — Django `LANGUAGE_CODE=pt-br`) e escopo;
- uma linha por cachorro, **subtotais por cliente** (negrito, fundo
  próprio) e **totais gerais** do mês (linha superior na cor da marca);
- **zebra** nas linhas de cachorros; cabeçalho da tabela repetido a
  cada quebra de página (`repeatRows=1`);
- **rodapé em toda página**: nome da aplicação, `gerado em dd/mm/aaaa
  hh:mm` em `America/Sao_Paulo` (`timezone.localtime` — PRD seção 10) e
  `Página N`.

Cores do design system (PRD seção 20 — tokens extraídos do tema):

| Uso | Token | Valor |
|---|---|---|
| Cabeçalho da tabela / linha do total | `.bg-primary` | `#3654D1` |
| Rodapé / subtítulo | `.text-muted` | `#64748B` |
| Zebra | superfície clara | `#F8F9FA` |
| Grid | borda neutra | `#DEE2E6` |

**Português**: acentos (ç/ã/õ/é…) renderizam com as fontes internas
Helvetica (WinAnsi) — sem fontes embutidas e sem dependência externa.
Cabeçalhos e rótulos em pt-br; validado por testes que extraem o texto
com PyPDF e comparam strings acentuadas.

## Geração síncrona × assíncrona

O PRD seção 21 exige geração **não bloqueante** "quando a geração puder
ser demorada". Este relatório é agregado (as mesmas duas queries da
página — RNF-003) e renderiza em milissegundos: o download responde
**direto com o PDF** (`HttpResponse` com `Content-Disposition:
attachment`). Se um relatório lento surgir (ex.: histórico multi-anual),
o padrão assíncrono das Sprints 11/12 se aplica — despachar task,
notificar ao concluir e entregar o arquivo por link — sem mudar o
serviço de dados.

## Nome do arquivo

```text
controle-mensal-YYYY-MM[-cliente-<pk>][-cachorro-<pk>].pdf
```

ASCII puro, determinístico, com os escopos opcionais embutidos.

## PyPDF

O `pypdf` é a biblioteca companheira da stack (PRD seções 7/21):

- **testes** (`reports/tests.py`): todo PDF gerado é aberto com
  `PdfReader` — os testes provam que o documento é um PDF válido
  (`%PDF`), paginável (`Página 1`) e com o conteúdo esperado (títulos,
  cabeçalhos acentuados, clientes/cachorros, subtotais, rodapé com
  fuso horário) extraindo o texto;
- **manutenção**: ferramenta para inspecionar documentos gerados em
  produção (`PdfReader(...).pages[i].extract_text()`).

## Testes (`reports/tests.py`)

Serviço (PDF válido via PyPDF, conteúdo pt-br, rodapé com
`America/Sao_Paulo`, escopos por cliente/cachorro excluem o que está
fora, mês vazio com mensagem) e view (login, permissão — `Leitura`
pode baixar, sem acesso → 403 —, `Content-Type`, `Content-Disposition`
com e sem escopos, padrão mês corrente) + o link "Baixar PDF" na
página de controle com os filtros repassados.
