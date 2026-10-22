"""Report views: PDF downloads (PRD section 21 — Sprint 13).

The monthly control report is generated **synchronously**: the data is
aggregate-based (the same two queries as the page — RNF-003) and renders
in milliseconds, so the download responds directly with the PDF. PRD
section 21 requires the non-blocking path only "quando a geração puder
ser demorada"; if a slow report ever appears, the Celery pattern from
Sprints 11/12 applies (dispatch + notification) — see docs/relatorios.md.
"""

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import HttpResponse
from django.utils import timezone
from django.views import View

from clients.models import Client
from dogs.models import Dog
from reports.services import build_monthly_control_pdf
from walks.services import month_bounds, parse_month


def _valid_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


class MonthlyControlPdfView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Monthly control (RF-011) as a PDF download."""

    # Same permission as the page the report mirrors (walks.view_walk).
    permission_required = 'walks.view_walk'

    def get(self, request):
        today = timezone.localdate()
        parsed = parse_month(request.GET.get('month')) or (
            today.year,
            today.month,
        )
        month_start, month_end = month_bounds(*parsed)

        client = Client.objects.filter(
            pk=_valid_int(request.GET.get('client'))
        ).first()
        dog = Dog.objects.filter(pk=_valid_int(request.GET.get('dog'))).first()

        content = build_monthly_control_pdf(
            month_start, month_end, client=client, dog=dog
        )

        filename = f'controle-mensal-{month_start:%Y-%m}'
        if client is not None:
            filename += f'-cliente-{client.pk}'
        if dog is not None:
            filename += f'-cachorro-{dog.pk}'
        filename += '.pdf'

        response = HttpResponse(content, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="{filename}"'
        )
        return response
