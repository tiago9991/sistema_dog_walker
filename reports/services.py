"""PDF report services (PRD section 21 — Sprint 13).

First report: the **monthly walk control** — the same RF-011 counters as
``/walks/controle/`` (reuses ``walks.services.monthly_control``, so the
PDF can never disagree with the page) rendered with ReportLab. PyPDF is
the companion library of the stack (PRD section 7): it validates the
generated documents (tests assert a parsable PDF with the expected
content) and is the maintenance tool for inspecting generated files.

Layout (landscape A4 — the table has nine columns):

- header: report title, period (pt-br month name), scope filters;
- one row per dog with the RF-011 counters + realization percentage,
  a bold subtotal row per client and a grand total row;
- zebra stripes on dog rows; subtotal/total rows carry their own
  backgrounds (commands are applied in order — they win over zebra);
- the table header repeats on page breaks (``repeatRows``);
- footer on every page: application name, generation timestamp in
  ``America/Sao_Paulo`` (PRD section 10) and the page number.

Colors follow the design system (PRD section 20): the primary brand
color (``bg-primary`` = #3654D1), muted gray (#64748B — ``text-muted``),
light zebra rows (#F8F9FA) and neutral grid lines. Portuguese accents
(ç/ã/õ...) render through the built-in Helvetica fonts (WinAnsi
encoding) — no embedded fonts required.
"""

from io import BytesIO

from django.utils import timezone
from django.utils.formats import date_format
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from walks.services import group_monthly_control_by_client, monthly_control

# Design system tokens (PRD section 20 — theme.min.css / bootstrap).
BRAND_COLOR = colors.HexColor('#3654D1')  # .bg-primary
MUTED_COLOR = colors.HexColor('#64748B')  # .text-muted
ZEBRA_COLOR = colors.HexColor('#F8F9FA')
GRID_COLOR = colors.HexColor('#DEE2E6')
SUBTOTAL_COLOR = colors.HexColor('#EEF0F9')  # soft brand tint

PAGE_SIZE = landscape(A4)
MARGIN = 12 * mm

REPORT_TITLE = 'Controle mensal de passeios'

# Column widths (landscape A4 usable width ≈ 794 pt).
COLUMN_WIDTHS = [140, 120, 62, 62, 62, 62, 72, 62, 90]


def _scope_label(client=None, dog=None):
    """Human-readable scope line for the report header."""
    parts = []
    if dog is not None:
        parts.append(f'cachorro {dog.name}')
    if client is not None:
        parts.append(f'cliente {client.name}')
    return ', '.join(parts) if parts else 'todos os clientes e cachorros'


def _styles():
    base = getSampleStyleSheet()
    return {
        'title': ParagraphStyle(
            'ReportTitle',
            parent=base['Title'],
            fontSize=16,
            spaceAfter=2,
            alignment=0,  # left-aligned (the sample Title is centered)
        ),
        'subtitle': ParagraphStyle(
            'ReportSubtitle',
            parent=base['Normal'],
            fontSize=10,
            textColor=MUTED_COLOR,
        ),
        'cell': ParagraphStyle(
            'ReportCell',
            parent=base['BodyText'],
            fontSize=8.5,
            leading=11,
        ),
        'cell_bold': ParagraphStyle(
            'ReportCellBold',
            parent=base['BodyText'],
            fontSize=8.5,
            leading=11,
            fontName='Helvetica-Bold',
        ),
    }


def _footer(canvas, document):
    """Page footer: application, generation timestamp and page number."""
    canvas.saveState()
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(MUTED_COLOR)
    generated = timezone.localtime().strftime('%d/%m/%Y %H:%M')
    tz_name = timezone.get_current_timezone_name()
    canvas.drawString(
        MARGIN,
        10 * mm,
        f'Sistema de Gestão para Dog Walker Inteligente — '
        f'gerado em {generated} ({tz_name})',
    )
    canvas.drawRightString(
        PAGE_SIZE[0] - MARGIN, 10 * mm, f'Página {document.page}'
    )
    canvas.restoreState()


def _counter_row(styles, label, dog_name, counters, bold=False):
    """One data row: client/dog labels as Paragraphs (wrap), numbers."""
    cell = styles['cell_bold'] if bold else styles['cell']
    return [
        Paragraph(label, cell),
        Paragraph(dog_name, cell),
        counters['contracted'],
        counters['scheduled'],
        counters['completed'],
        counters['cancelled'],
        counters['missed'],
        counters['remaining'],
        f"{counters['progress']}%",
    ]


def build_monthly_control_pdf(month_start, month_end, client=None, dog=None):
    """Render the monthly control report (RF-011) as PDF bytes."""
    rows, totals = monthly_control(
        month_start, month_end, client=client, dog=dog
    )
    client_groups = group_monthly_control_by_client(rows)

    styles = _styles()

    story = [
        Paragraph(REPORT_TITLE, styles['title']),
        Paragraph(
            f"Período: {date_format(month_start, 'F Y')} — "
            f"Escopo: {_scope_label(client=client, dog=dog)}",
            styles['subtitle'],
        ),
        Spacer(1, 6 * mm),
    ]

    data = [
        [
            'Cliente',
            'Cachorro',
            'Contratados',
            'Previstos',
            'Realizados',
            'Cancelados',
            'Não realizados',
            'Restantes',
            'Realização',
        ]
    ]
    style_commands = [
        ('BACKGROUND', (0, 0), (-1, 0), BRAND_COLOR),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('LEADING', (0, 0), (-1, -1), 11),
        ('GRID', (0, 0), (-1, -1), 0.4, GRID_COLOR),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]

    if not rows:
        data.append(
            [
                Paragraph(
                    'Nenhum passeio ou programação no período.',
                    styles['cell'],
                ),
                '', '', '', '', '', '', '', '',
            ]
        )
    else:
        subtotal_indices = []
        for group in client_groups:
            client = group['client']
            client_label = client.name + (
                '' if client.is_active else ' (desativado)'
            )
            for row in group['rows']:
                dog_label = row['dog'].name + (
                    '' if row['dog'].is_active else ' (desativado)'
                )
                data.append(_counter_row(styles, client_label, dog_label, row))
            data.append(
                _counter_row(
                    styles,
                    f'Totais de {client.name}',
                    '',
                    group['totals'],
                    bold=True,
                )
            )
            subtotal_indices.append(len(data) - 1)

        data.append(
            _counter_row(styles, 'Totais do mês', '', totals, bold=True)
        )
        grand_total_index = len(data) - 1

        # Zebra stripes on the dog rows, painted BEFORE the subtotal and
        # grand-total backgrounds so those win (commands apply in order).
        if grand_total_index > 1:
            style_commands.append(
                (
                    'ROWBACKGROUNDS',
                    (0, 1),
                    (-1, grand_total_index - 1),
                    [colors.white, ZEBRA_COLOR],
                )
            )
        for index in subtotal_indices:
            style_commands.append(
                ('BACKGROUND', (0, index), (-1, index), SUBTOTAL_COLOR)
            )
        style_commands.extend(
            [
                (
                    'BACKGROUND',
                    (0, grand_total_index),
                    (-1, grand_total_index),
                    ZEBRA_COLOR,
                ),
                (
                    'LINEABOVE',
                    (0, grand_total_index),
                    (-1, grand_total_index),
                    0.8,
                    BRAND_COLOR,
                ),
            ]
        )

    table = Table(data, colWidths=COLUMN_WIDTHS, repeatRows=1)
    table.setStyle(TableStyle(style_commands))
    story.append(table)

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=PAGE_SIZE,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=18 * mm,
        title=f'{REPORT_TITLE} — {month_start:%m/%Y}',
    )
    document.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()
