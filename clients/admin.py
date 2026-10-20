"""Django Admin for the clients domain (PRD sections 4.2 and 8.2)."""

from django.contrib import admin

from clients.models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'phone', 'email')
    readonly_fields = ('created_at', 'updated_at', 'deactivated_at')
