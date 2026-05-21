# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Dev local:**
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Docker (producción):**
```bash
make build    # construye imagen
make up       # levanta en background en puerto 8001
make logs     # ver logs
make restart  # tras git pull + make build
```

Variables de entorno requeridas en producción: `ADMIN_USER`, `ADMIN_PASSWORD`, `SECRET_KEY` (en `.env`).

## Architecture

Two files contain all logic:

- **`main.py`** — FastAPI app: session auth, all routes (public display, admin CRUD, file uploads), and `/api/data` which is the only endpoint consumed by the frontend.
- **`database.py`** — SQLAlchemy models + `init_db()` which seeds the DB on first run.

**Models:** `Settings` (rotation timer), `Background` (4 slots, id 1–4), `Category` (fixed claves: ron/whisky/cerveza/sangria), `ProductItem` (belongs to a category, has `orden` for sorting).

**Category–background mapping is positional:** `ORDEN_CATEGORIAS = ["ron", "whisky", "cerveza", "sangria"]` in `main.py` maps index 0–3 to Background rows 1–4. This order is used in `/api/data`, the admin panel, and implicitly in the frontend's 4 `bg-capa` divs.

**`/api/data` response shape:**
```json
{
  "tiempo_rotacion": 10,
  "backgrounds": ["url_or_null", ...],
  "pantallas": [
    {"capa_idx": 0, "categoria_nombre": "Ron", "items": [...]}
  ]
}
```
A category with >~15 items is split into multiple `pantallas` (same `capa_idx`) using `round(n/15)` screens distributed evenly.

**Frontend (`templates/public.html`)** is a single self-contained HTML file with no build step. It fetches `/api/data` on load and silently every 30 s. It cycles through `pantallas[]` using CSS opacity crossfades: the background (`bg-capa` divs) only transitions when `capa_idx` changes between consecutive pantallas, so same-category pages only fade the content overlay.

**Admin** (`/admin`) uses server-side Jinja2 templates and form POSTs — no JS framework. Session auth via `itsdangerous` SessionMiddleware; credentials from env vars.

**Uploads** are stored in `static/uploads/` as `bg_1.jpg`–`bg_4.jpg` (overwritten on re-upload). The `static/` directory is mounted as a Docker volume alongside `sanez.db`.
