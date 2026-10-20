"""Django Admin for the scheduling domain (PRD sections 4.2 and 8.2)."""

from django.contrib import admin

from scheduling.models import WalkSchedule


@admin.register(WalkSchedule)
class WalkScheduleAdmin(admin.ModelAdmin):
    list_display = (
        'dog',
        'frequency',
        'weekday_summary',
        'start_date',
        'end_date',
        'is_active',
        'created_at',
        'updated_at',
    )
    list_filter = ('is_active', 'frequency', 'dog')
    search_fields = ('dog__name', 'dog__client__name')
    list_select_related = ('dog', 'dog__client')
    readonly_fields = ('created_at', 'updated_at', 'deactivated_at')

    @admin.display(description='dias')
    def weekday_summary(self, obj):
        return obj.weekday_summary
