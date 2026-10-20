# ADR-0004 — Design system Duralux como referência visual oficial

- **Status:** Aceito
- **Data:** 2026-10-20 (Sprint 0)
- **Contexto:** PRD seção 20; `design_system/design-system.html`

## Decisão

O arquivo `design_system/design-system.html` (baseado no tema Duralux:
Bootstrap 5 + camada `nxl-*`) é a única referência visual oficial. Toda
interface deve respeitar suas cores, tipografia, componentes, espaçamentos,
estados e padrões de interação. Nenhum estilo pode contradizer o design
system.

## Síntese técnica extraída da referência

- **Fontes:** Inter (corpo, `0.84rem`, line-height 1.6, cor `#6b7885`);
  títulos `h1`–`h6` peso 700 cor `#283c50`; alternativa Roboto Slab via
  customizador. Escala com utilitários `.fs-*`.
- **Cores semânticas:** primary `#3454d1`; success `#17c666`; danger
  `#ea4d4d`; warning `#ffa21d`; info `#3dc7be`; teal `#41b2c4`; indigo
  `#6610f2`; dark `#283c50`; fundo `#f3f4f6`; borda `#e6e9ed`. Variantes
  `.bg-soft-*` para badges/avatares.
- **Shell:** sidebar `nav.nxl-navigation` + `.nxl-navbar`/`.nxl-link`
  (submenus `.nxl-hasmenu`/`.nxl-submenu`); `.page-header` com
  `.page-header-title`, breadcrumb e itens à direita (daterangepicker,
  filtro); conteúdo em `.card .stretch .stretch-full` com `.card-title`.
- **Componentes:** botões `btn btn-*` (primary/danger/success/warning/info,
  outline, light-brand); `form-control`/`form-label`/`form-select`;
  `table table-hover`; badges; avatars (`.avatar-text`, `avatar-xs`);
  paginação com `.bi .bi-*`; tooltips; padrão de KPIs (footer stats);
  gráficos ApexCharts + Circle Progress.
- **Ícones:** Feather Icons (`.feather-*`) como principal.
- **Motion:** transições `all .3s ease`; sidebar recolhida/expandida via
  `#menu-mini-button`/`#menu-expend-button`; mobile `.hamburger--arrowturn`.

## Consequências

- Templates e CSS customizados serão construídos sobre Bootstrap 5 + classes
  do tema, reutilizando os assets em `design_system/refs/duralux/`.
- Aplicação prática do design system ocorre a partir da Sprint 3 (páginas de
  autenticação) e é validada na Sprint 10 (dashboard) e Sprint 23
  (responsividade).
