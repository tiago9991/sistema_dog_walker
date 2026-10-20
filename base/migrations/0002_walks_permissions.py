"""Extend the authorization groups with the scheduling/walks permissions
(Sprint 6/7 — PRD section 4.4).

Same mapping rules as ``base.0001_groups``: full business CRUD for
``Operação`` (no ``delete_*`` — history must be preserved), read-only for
``Leitura``.
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

ADDED_GROUP_PERMISSIONS = {
    'Operação': {
        'scheduling': ('view_walkschedule', 'add_walkschedule', 'change_walkschedule'),
        'walks': ('view_walk', 'add_walk', 'change_walk'),
    },
    'Leitura': {
        'scheduling': ('view_walkschedule',),
        'walks': ('view_walk',),
    },
}


def add_permissions(apps, schema_editor):
    from django.apps import apps as global_apps
    from django.contrib.auth.models import Group, Permission

    for app_label in ('scheduling', 'walks'):
        create_permissions(global_apps.get_app_config(app_label), verbosity=0)

    for group_name, app_permissions in ADDED_GROUP_PERMISSIONS.items():
        group, _ = Group.objects.get_or_create(name=group_name)
        for app_label, codenames in app_permissions.items():
            for codename in codenames:
                group.permissions.add(
                    Permission.objects.get(
                        content_type__app_label=app_label, codename=codename
                    )
                )


def remove_permissions(apps, schema_editor):
    from django.contrib.auth.models import Group, Permission

    for group_name, app_permissions in ADDED_GROUP_PERMISSIONS.items():
        if not Group.objects.filter(name=group_name).exists():
            continue
        group = Group.objects.get(name=group_name)
        for app_label, codenames in app_permissions.items():
            for codename in codenames:
                group.permissions.remove(
                    Permission.objects.get(
                        content_type__app_label=app_label, codename=codename
                    )
                )


class Migration(migrations.Migration):
    dependencies = [
        ('base', '0001_groups'),
        ('scheduling', '0001_initial'),
        ('walks', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(add_permissions, remove_permissions),
    ]
