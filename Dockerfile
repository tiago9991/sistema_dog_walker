# syntax=docker/dockerfile:1
# Local development image (Sprint 2). The production stack (Sprint 17)
# reuses this image and overrides the command with the production server.

FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first for layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application code (.dockerignore keeps .env and artifacts out of the image).
COPY . .

EXPOSE 8000

# PRD section 17: wait for the database, advisory lock + migrations,
# collectstatic --clear, then exec the command below (the dev server).
ENTRYPOINT ["python", "scripts/entrypoint.py"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
