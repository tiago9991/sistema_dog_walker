"""Reports tests (Sprint 13 — PRD section 21): PDF generation validated
with PyPDF (the stack's companion library — the tests prove the output
is a parsable PDF with the expected pt-br content and timezone footer),
scope filters, and the download view permissions/headers."""

from datetime import date
from io import BytesIO

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from pypdf import PdfReader

from clients.models import Client
from dogs.models import Dog
from reports.services import build_monthly_control_pdf
from scheduling.models import WalkSchedule
from walks.models import Walk
from walks.services import month_bounds

MONTH_START, MONTH_END = month_bounds(2026, 10)


def pdf_pages(content):
    """Parse PDF bytes with PyPDF → list of pages (validation + text)."""
    return PdfReader(BytesIO(content)).pages


def pdf_text(content):
    """Full text of the PDF (all pages) for content assertions."""
    return '\n'.join(page.extract_text() for page in pdf_pages(content))


class ReportTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.operator = User.objects.create_user('operador', password='op-senha-123')
        cls.operator.groups.add(Group.objects.get(name='Operação'))
        cls.reader = User.objects.create_user('leitor', password='rd-senha-123')
        cls.reader.groups.add(Group.objects.get(name='Leitura'))
        cls.no_access = User.objects.create_user('sem-acesso', password='na-senha-123')

        cls.client_a = Client.objects.create(name='Cliente A')
        cls.dog_a = Dog.objects.create(client=cls.client_a, name='Rex')
        cls.client_b = Client.objects.create(name='Cliente B')
        cls.dog_b = Dog.objects.create(client=cls.client_b, name='Bidu')

    def login(self, user):
        self.client.force_login(user)

    def seed_month(self):
        """Deterministic October 2026 data (no generation-window math)."""
        WalkSchedule.objects.create(
            dog=self.dog_a,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 31),
            monday=True,
            wednesday=True,
        )
        WalkSchedule.objects.create(
            dog=self.dog_b,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 31),
            tuesday=True,
        )
        Walk.objects.create(
            dog=self.dog_a, date=date(2026, 10, 5), status=Walk.STATUS_COMPLETED
        )
        Walk.objects.create(
            dog=self.dog_b, date=date(2026, 10, 6), status=Walk.STATUS_CANCELLED
        )
        Walk.objects.create(
            dog=self.dog_a, date=date(2026, 10, 12), status=Walk.STATUS_SCHEDULED
        )


class MonthlyControlPdfTests(ReportTestBase):
    """The service output, validated with PyPDF (PRD section 21)."""

    def test_output_is_a_valid_pdf(self):
        self.seed_month()
        content = build_monthly_control_pdf(MONTH_START, MONTH_END)
        self.assertTrue(content.startswith(b'%PDF'))
        pages = pdf_pages(content)
        self.assertGreaterEqual(len(pages), 1)

    def test_pdf_contains_title_headers_and_data(self):
        self.seed_month()
        text = pdf_text(build_monthly_control_pdf(MONTH_START, MONTH_END))
        # Title + pt-br period.
        self.assertIn('Controle mensal de passeios', text)
        self.assertIn('Outubro 2026', text)
        self.assertIn('todos os clientes e cachorros', text)
        # Table headers (pt-br with accents — Helvetica/WinAnsi).
        for header in (
            'Contratados',
            'Previstos',
            'Realizados',
            'Cancelados',
            'Não realizados',
            'Restantes',
            'Realização',
        ):
            self.assertIn(header, text, msg=header)
        # Data: both clients/dogs, per-client subtotals and grand totals.
        self.assertIn('Cliente A', text)
        self.assertIn('Rex', text)
        self.assertIn('Cliente B', text)
        self.assertIn('Bidu', text)
        self.assertIn('Totais de Cliente A', text)
        self.assertIn('Totais de Cliente B', text)
        self.assertIn('Totais do mês', text)

    def test_pdf_footer_has_timezone_and_page_number(self):
        self.seed_month()
        text = pdf_text(build_monthly_control_pdf(MONTH_START, MONTH_END))
        self.assertIn('Sistema de Gestão para Dog Walker Inteligente', text)
        self.assertIn('gerado em', text)
        self.assertIn('America/Sao_Paulo', text)  # PRD timezone (section 10)
        self.assertIn('Página 1', text)

    def test_pdf_client_scope_excludes_other_clients(self):
        self.seed_month()
        text = pdf_text(
            build_monthly_control_pdf(MONTH_START, MONTH_END, client=self.client_a)
        )
        self.assertIn('cliente Cliente A', text)
        self.assertIn('Rex', text)
        self.assertNotIn('Cliente B', text)
        self.assertNotIn('Bidu', text)

    def test_pdf_dog_scope_excludes_other_dogs(self):
        self.seed_month()
        text = pdf_text(
            build_monthly_control_pdf(MONTH_START, MONTH_END, dog=self.dog_b)
        )
        self.assertIn('cachorro Bidu', text)
        self.assertNotIn('Rex', text)

    def test_pdf_without_data_renders_message(self):
        content = build_monthly_control_pdf(MONTH_START, MONTH_END)
        self.assertTrue(content.startswith(b'%PDF'))
        text = pdf_text(content)
        # The message Paragraph wraps inside the column — assert the
        # unwrapped portion.
        self.assertIn('Nenhum passeio', text)
        self.assertIn('no período', text)


class MonthlyControlPdfViewTests(ReportTestBase):
    def test_requires_login(self):
        response = self.client.get(reverse('reports:monthly_control_pdf'))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('reports:monthly_control_pdf')}",
            fetch_redirect_response=False,
        )

    def test_requires_view_walk_permission(self):
        self.login(self.no_access)
        response = self.client.get(reverse('reports:monthly_control_pdf'))
        self.assertEqual(response.status_code, 403)

    def test_reader_can_download(self):
        self.login(self.reader)
        response = self.client.get(
            reverse('reports:monthly_control_pdf'), {'month': '2026-10'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_download_headers_and_filename(self):
        self.seed_month()
        self.login(self.operator)
        response = self.client.get(
            reverse('reports:monthly_control_pdf'), {'month': '2026-10'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Disposition'],
            'attachment; filename="controle-mensal-2026-10.pdf"',
        )
        text = pdf_text(response.content)
        self.assertIn('Totais de Cliente A', text)

    def test_download_filename_includes_scopes(self):
        self.seed_month()
        self.login(self.operator)
        response = self.client.get(
            reverse('reports:monthly_control_pdf'),
            {
                'month': '2026-10',
                'client': self.client_a.pk,
                'dog': self.dog_a.pk,
            },
        )
        self.assertEqual(
            response['Content-Disposition'],
            'attachment; filename='
            f'"controle-mensal-2026-10-cliente-{self.client_a.pk}'
            f'-cachorro-{self.dog_a.pk}.pdf"',
        )

    def test_view_defaults_to_current_month(self):
        self.login(self.operator)
        response = self.client.get(reverse('reports:monthly_control_pdf'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('controle-mensal-', response['Content-Disposition'])


class ControlPageReportTests(ReportTestBase):
    """The monthly control page links the PDF report (Sprint 13)."""

    def test_control_page_links_pdf_with_filters(self):
        self.login(self.operator)
        response = self.client.get(
            reverse('walks:control'),
            {'month': '2026-10', 'client': self.client_a.pk},
        )
        self.assertContains(response, 'Baixar PDF')
        self.assertContains(
            response,
            f"{reverse('reports:monthly_control_pdf')}?month=2026-10"
            f"&client={self.client_a.pk}",
        )
