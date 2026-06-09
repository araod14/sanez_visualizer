# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Dev local:**
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
DEV_MODE=1 SUPER_ADMIN_EMAIL=admin@local SUPER_ADMIN_PASSWORD=admin \
  uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
`DEV_MODE=1` permite arrancar sin `SECRET_KEY` (genera una clave efímera) y
desactiva el flag `Secure` de la cookie de sesión para poder usar HTTP local.

**Docker (producción):**
```bash
make build    # construye imagen
make up       # levanta en background en puerto 8001
make logs     # ver logs
make restart  # tras git pull + make build
make migrate  # one-shot: migra una DB single-tenant vieja al esquema multi-tenant
```

Variables de entorno en `.env`: `SUPER_ADMIN_EMAIL`, `SUPER_ADMIN_PASSWORD`,
`SECRET_KEY`. Los nombres viejos `ADMIN_USER` / `ADMIN_PASSWORD` siguen
funcionando como fallback para el bootstrap del super-admin.

**Seguridad / sesión** (todas opcionales con defaults seguros):
- `SECRET_KEY` — **obligatoria en producción**; sin ella el arranque falla salvo `DEV_MODE=1`.
- `DEV_MODE` — `1` para desarrollo local (clave efímera + cookie sin `Secure`).
- `SESSION_HTTPS_ONLY` — flag `Secure` de la cookie. Default `1` fuera de `DEV_MODE`.
  **Si producción NO está detrás de HTTPS, poné `SESSION_HTTPS_ONLY=0`** o el login no funcionará.
- `SESSION_SAME_SITE` — `lax` (default) / `strict` / `none`.
- `LOGIN_MAX_ATTEMPTS` (default 5) y `LOGIN_WINDOW_SECONDS` (default 300) — rate limit de login por IP, en memoria por proceso.

**Protección CSRF:** dependencia global `verify_csrf` valida un token de sesión
(`csrf_token`) en toda petición mutante. Las plantillas lo reciben vía
`context_processor`; cada `<form method="post">` debe incluir
`<input type="hidden" name="csrf_token" value="{{ csrf_token }}">`.

## Architecture

Es **multi-tenant** desde la v1: un super-admin da de alta cuentas; cada
usuario gestiona sus categorías, productos y backgrounds; el público consume
`/menu/<slug>`. Toda la lógica vive en dos archivos:

- **`main.py`** — FastAPI app con SessionMiddleware. Tres familias de rutas:
  - **Públicas:** `/login`, `/logout`, `/menu/{slug}` (HTML), `/api/data/{slug}` (JSON consumido por el frontend).
  - **Usuario** (`require_user`): `/admin` y CRUD de categorías/items/uploads. Todas las queries filtran por `user.id` y `_get_owned_category` / `_get_owned_item` verifican ownership antes de mutar.
  - **Super-admin** (`require_super_admin`): `/super` (lista), `/super/users[/...]` (CRUD), `/super/users/{id}/impersonate` (cambia `session["user_id"]` guardando `session["impersonator_id"]`), y `/admin/stop-impersonating` (restaura).
- **`database.py`** — modelos SQLAlchemy + `init_db()` que solo crea tablas y bootstrapea el super-admin si no existe. Hash de contraseñas con `bcrypt` directo (truncado a 72 bytes en `_coerce_password`).

**Modelos:**
- `User` (id, email, slug único, nombre_negocio, password_hash, is_active, is_super_admin, tiempo_rotacion_segundos).
- `Category` (id, user_id, nombre, orden, background_path). UniqueConstraint(user_id, orden).
- `ProductItem` (id, category_id, nombre, precio: **String** — no Float; el frontend lo muestra tal cual).

**Slug:** validado por `SLUG_REGEX` (`^[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?$`) + `RESERVED_SLUGS` (`admin`, `super`, `api`, `login`, `logout`, `static`, `menu`).

**`/api/data/{slug}` response shape:**
```json
{
  "tiempo_rotacion": 10,
  "backgrounds": ["/static/uploads/<user_id>/cat_<id>.jpg", null, ...],
  "pantallas": [
    {"capa_idx": 0, "categoria_nombre": "Cervezas", "items": [...]}
  ]
}
```
`capa_idx` es el índice posicional de la categoría en su orden, y `backgrounds[capa_idx]` es su imagen (puede ser `null`). Una categoría con >~15 items se parte en varias `pantallas` (mismo `capa_idx`) usando `round(n/15)`.

**Frontend (`templates/public.html`)** es un único HTML autocontenido sin build. Lee `data-slug` del `<body>`, fetchea `/api/data/{slug}` al cargar y silenciosamente cada 30 s, y crea los `bg-capa` divs **dinámicamente** según `backgrounds.length` (cualquier cantidad de categorías, no más 4 fijos). Cycla por `pantallas[]` con crossfades CSS: el background sólo transiciona cuando `capa_idx` cambia entre pantallas consecutivas.

**Admin** (`/admin`, `templates/admin/dashboard.html`) usa Jinja2 + form POSTs, sin framework JS. Itera sobre `user.categorias` (dinámico). El super-admin (`templates/super/users_list.html`, `templates/super/user_form.html`) sigue el mismo patrón.

**Uploads:** se almacenan en `static/uploads/<user_id>/cat_<category_id>.<ext>`. Al borrar la categoría se borra el archivo; al borrar el usuario, se borra su carpeta entera con `shutil.rmtree`. El volumen `./static/uploads` montado en Docker cubre toda la jerarquía.

**Migración legacy → multi-tenant:** `scripts/migrate_to_multitenant.py` detecta el esquema viejo (tabla `categories` con PK `clave`), lee la data con SQL crudo, dropea las tablas viejas, crea el esquema nuevo y reinjecta todo bajo un usuario "legacy" (`LEGACY_SLUG`, default `demo`). Es idempotente.
