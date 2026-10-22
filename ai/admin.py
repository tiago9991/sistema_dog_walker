"""Django Admin for the AI domain (PRD sections 4.2, 8.2 and 19)."""

from django.contrib import admin

from ai.models import AIAnalysis


@admin.register(AIAnalysis)
class AIAnalysisAdmin(admin.ModelAdmin):
    list_display = (
        'kind',
        'month',
        'client',
        'status',
        'requested_by',
        'created_at',
        'completed_at',
    )
    list_filter = ('kind', 'status')
    search_fields = ('month', 'client__name', 'result', 'error')
    list_select_related = ('client', 'requested_by')
    readonly_fields = (
        'input_summary',
        'result',
        'error',
        'completed_at',
        'created_at',
        'updated_at',
    )
