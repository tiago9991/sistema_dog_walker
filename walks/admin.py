"""Django Admin for the walks domain (PRD sections 4.2 and 8.2)."""

from django.contrib import admin

from walks.models import Walk


@admin.register(Walk)
class WalkAdmin(admin.ModelAdmin):
    list_display = (
        'date',
        'dog',
        'client_name',
        'status',
        'status_changed_at',
        'created_at',
        'updated_at',
    )
    list_filter = ('status', 'date', 'dog')
    search_fields = ('dog__name', 'dog__client__name', 'notes')
    list_select_related = ('dog', 'dog__client')
    readonly_fields = ('status_changed_at', 'created_at', 'updated_at')

    @admin.display(description='cliente', ordering='dog__client__name')
    def client_name(self, obj):
        return obj.dog.client.name
