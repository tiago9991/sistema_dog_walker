"""Django Admin for the dogs domain (PRD sections 4.2 and 8.2)."""

from django.contrib import admin

from dogs.models import Dog


@admin.register(Dog)
class DogAdmin(admin.ModelAdmin):
    list_display = ('name', 'client', 'breed', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'client')
    search_fields = ('name', 'breed', 'client__name')
    list_select_related = ('client',)
    readonly_fields = ('created_at', 'updated_at', 'deactivated_at')
