"""Generate the planned walks from the active schedules (PRD RF-005).

Idempotent: safe to run repeatedly (re-runs create nothing new). Scheduled
for background execution via Celery in Sprint 11, when the broker exists
(PRD section 18).
"""

from django.core.management.base import BaseCommand

from walks.services import GENERATION_HORIZON_DAYS, GENERATION_LOOKBACK_DAYS, generate_walks


class Command(BaseCommand):
    help = (
        'Gera os passeios previstos a partir das programações ativas '
        '(idempotente).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--lookback',
            type=int,
            default=GENERATION_LOOKBACK_DAYS,
            help=f'Dias para trás da janela de geração (padrão: {GENERATION_LOOKBACK_DAYS}).',
        )
        parser.add_argument(
            '--horizon',
            type=int,
            default=GENERATION_HORIZON_DAYS,
            help=f'Dias para frente da janela de geração (padrão: {GENERATION_HORIZON_DAYS}).',
        )

    def handle(self, *args, **options):
        stats = generate_walks(
            lookback_days=options['lookback'],
            horizon_days=options['horizon'],
        )
        self.stdout.write(
            self.style.SUCCESS(
                'Geração concluída: {schedules} programação(ões) considerada(s), '
                '{created} passeio(s) criado(s), {existing} já existente(s).'.format(
                    **stats
                )
            )
        )
