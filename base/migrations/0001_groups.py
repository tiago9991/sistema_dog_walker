"""Create the authorization groups (Sprint 3 — PRD section 4).

Groups:
- ``Operação``: full business CRUD over clients and dogs (no Django Admin
  access, no hard deletes);
- ``Leitura``: read-only over clients and dogs.

Deactivation/activation (soft) maps to the ``change_*`` permission;
``delete_*`` is intentionally not granted to any group — history must be
preserved (PRD RF-002/RF-003).
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

GROUP_PERMISSIONS = {
    'Operação': {
        'clients': ('view_client', 'add_client', 'change_client'),
        'dogs': ('view_dog', 'add_dog', 'change_dog'),
    },
    'Leitura': {
        'clients': ('view_client',),
        'dogs': ('view_dog',),
    },
}


def create_groups(apps, schema_editor):
    # create_permissions requires the real AppConfig (the historical registry
    # inside migrations only provides stubs).
    from django.apps import apps as global_apps
    from django.contrib.auth.models import Group, Permission

    # Permissions are created post-migrate by a signal; inside a migration
    # they must be created explicitly before being assignable.
    for app_label in ('clients', 'dogs'):
        create_permissions(global_apps.get_app_config(app_label), verbosity=0)

    for group_name, app_permissions in GROUP_PERMISSIONS.items():
        group = Group.objects.create(name=group_name)
        for app_label, codenames in app_permissions.items():
            for codename in codenames:
                group.permissions.add(
                    Permission.objects.get(
                        content_type__app_label=app_label, codename=codename
                    )
                )


def remove_groups(apps, schema_editor):
    from django.contrib.auth.models import Group

    Group.objects.filter(name__in=tuple(GROUP_PERMISSIONS)).delete()


class Migration(migrations.Migration):
    dependencies = [
        # Groups need the auth tables (final state) and the domain models'
        # permissions (clients/dogs 0001).
        ('auth', '0012_alter_user_first_name_max_length'),
        ('clients', '0001_initial'),
        ('dogs', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_groups, remove_groups),
    ]
