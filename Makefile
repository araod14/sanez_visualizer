.PHONY: build up down restart logs ps dev install

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

# Ejecuta la migración one-shot del esquema single-tenant → multi-tenant.
# Requiere que el contenedor esté arriba (make up) y que sanez.db exista.
migrate:
	docker compose exec app python scripts/migrate_to_multitenant.py

ps:
	docker compose ps

# ── Desarrollo local (sin Docker) ──────────────────────────────────────────
install:
	pip install -r requirements.txt

dev:
	DEV_MODE=1 venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload
