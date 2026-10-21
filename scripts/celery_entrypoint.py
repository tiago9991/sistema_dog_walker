"""Celery entrypoint (PRD section 17 — Sprint 11).

Steps:
    1. wait for the database;
    2. exec the given command (``celery -A core worker``/``beat``).

Celery Worker and Celery Beat must NOT run migrations or collectstatic
(PRD section 17) — those belong to the web entrypoint
(``scripts/entrypoint.py``) only, which serializes them with a PostgreSQL
advisory lock.

Runs inside the application container as the Docker ENTRYPOINT. The
Celery command is passed through ``CMD`` and becomes ``sys.argv[1:]``:
``python scripts/celery_entrypoint.py celery -A core worker -l info``.
"""

import os
import sys

# Make the project root importable (``core``, ``base``, ...) regardless of
# the working directory (same as scripts/entrypoint.py).
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def main() -> None:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

    import django

    django.setup()

    # Step 1 — block until the database accepts connections (reuses the
    # web entrypoint's helper; it contains only this function's sibling
    # logic and never runs migrations).
    from scripts.entrypoint import wait_for_database

    wait_for_database()

    celery_command = sys.argv[1:]
    if not celery_command:
        raise SystemExit('celery-entrypoint: missing celery command')

    # Step 2 — replace this process with the Celery worker/beat.
    print(f'celery-entrypoint: starting: {" ".join(celery_command)}', flush=True)
    os.execvp(celery_command[0], celery_command)


if __name__ == '__main__':
    main()
