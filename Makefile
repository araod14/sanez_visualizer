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

ps:
	docker compose ps

# ── Desarrollo local (sin Docker) ──────────────────────────────────────────
install:
	pip install -r requirements.txt

dev:
	venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload
