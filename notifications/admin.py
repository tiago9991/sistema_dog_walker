"""Django Admin for the notifications domain (PRD sections 4.2 and 8.2)."""

from django.contrib import admin

from notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'recipient', 'level', 'is_read', 'created_at')
    list_filter = ('level', 'is_read')
    search_fields = ('title', 'message', 'recipient__username')
    list_select_related = ('recipient',)
    readonly_fields = ('read_at', 'created_at', 'updated_at')
