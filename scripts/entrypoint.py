"""Container entrypoint (PRD section 17).

Steps:
    1. wait for the database;
    2. acquire a PostgreSQL advisory lock;
    3. run migrations;
    4. release the lock;
    5. run ``collectstatic --clear``;
    6. exec the application server.

Runs inside the application container as the Docker ENTRYPOINT. The
application command is passed through ``CMD`` and becomes ``sys.argv[1:]``:
``python scripts/entrypoint.py python manage.py runserver 0.0.0.0:8000``.

Celery Worker and Celery Beat must NOT use this entrypoint: they wait for
the database but do not run migrations or collectstatic (PRD section 17).
"""

import os
import sys
import time

# Running as ``python scripts/entrypoint.py`` makes the script's directory
# (not the project root) the first sys.path entry — make the project root
# importable (``core``, ``base``, ...) regardless of the working directory.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Advisory lock shared by every replica that may run migrations, so that
# concurrent entrypoints (e.g. multiple replicas starting at once) cannot
# migrate in parallel. Arbitrary fixed bigint; must not collide with another
# pg_advisory_lock user in the same database.
MIGRATIONS_ADVISORY_LOCK_KEY = 424_242

WAIT_DB_TIMEOUT = int(os.environ.get("ENTRYPOINT_DB_TIMEOUT", "60"))
WAIT_DB_INTERVAL = 2.0


def wait_for_database():
    """Step 1 — block until the database accepts connections."""
    from django.db import connection

    deadline = time.monotonic() + WAIT_DB_TIMEOUT
    while True:
        try:
            connection.ensure_connection()
            return
        except Exception as exc:  # any driver error means "not ready yet"
            if time.monotonic() >= deadline:
                raise SystemExit(
                    f"entrypoint: database not reachable after "
                    f"{WAIT_DB_TIMEOUT}s: {exc}"
                ) from exc
            print(
                f"entrypoint: waiting for database "
                f"({exc.__class__.__name__})...",
                flush=True,
            )
            time.sleep(WAIT_DB_INTERVAL)


def is_postgresql() -> bool:
    from django.db import connection

    return connection.settings_dict["ENGINE"].endswith("postgresql")


def migrate_with_advisory_lock():
    """Steps 2-4 — serialize migrations, then migrate, then release."""
    from django.core.management import call_command
    from django.db import connection

    if not is_postgresql():
        call_command("migrate", interactive=False)
        return

    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_lock(%s)", [MIGRATIONS_ADVISORY_LOCK_KEY])
    try:
        call_command("migrate", interactive=False)
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_unlock(%s)", [MIGRATIONS_ADVISORY_LOCK_KEY]
            )


def collectstatic():
    """Step 5 — refresh static files (``collectstatic --clear``)."""
    from django.core.management import call_command

    call_command("collectstatic", interactive=False, clear=True, verbosity=0)


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

    import django

    django.setup()

    wait_for_database()
    migrate_with_advisory_lock()
    collectstatic()

    app_command = sys.argv[1:]
    if not app_command:
        raise SystemExit("entrypoint: missing application command")

    # Step 6 — replace this process with the application server.
    print(f"entrypoint: starting: {' '.join(app_command)}", flush=True)
    os.execvp(app_command[0], app_command)


if __name__ == "__main__":
    main()
