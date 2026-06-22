.PHONY: build up down restart logs ps dev install test lint migrate-db

# ── Docker ─────────────────────────────────────────────────────────────────
build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose down && docker compose up -d

logs:
	docker compose logs -f

# Migración one-shot del esquema single-tenant → multi-tenant (legacy).
# Requiere que el contenedor esté arriba (make up) y que sanez.db exista.
migrate:
	docker compose exec app python scripts/migrate_to_multitenant.py

ps:
	docker compose ps

# ── Desarrollo local (sin Docker) ──────────────────────────────────────────
install:
	venv/bin/pip install -e ".[dev]"

PORT ?= 8000
dev:
	DEV_MODE=1 venv/bin/uvicorn main:app --host 0.0.0.0 --port $(PORT) --reload

test:
	venv/bin/python -m pytest

lint:
	venv/bin/ruff check . && venv/bin/ruff format --check .

# Aplica las migraciones versionadas de Alembic a la DB local.
migrate-db:
	DEV_MODE=1 venv/bin/alembic upgrade head
