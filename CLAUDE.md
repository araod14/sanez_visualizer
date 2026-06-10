# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Dev local:**
```bash
python3 -m venv venv && source venv/bin/activate
make install            # pip install -e ".[dev]"  (deps + pytest/ruff)
DEV_MODE=1 SUPER_ADMIN_EMAIL=admin@local SUPER_ADMIN_PASSWORD=admin \
  uvicorn main:app --host 0.0.0.0 --port 8000 --reload   # o: make dev
```
`DEV_MODE=1` permite arrancar sin `SECRET_KEY` (genera una clave efímera) y
desactiva el flag `Secure` de la cookie de sesión para poder usar HTTP local.
Las dependencias y la config de herramientas (ruff, pytest) viven en
`pyproject.toml` (ya no hay `requirements.txt`).

**Tests / calidad:**
```bash
make test     # pytest (tests/ con engine in-memory; no toca la DB real)
make lint     # ruff check + ruff format --check
```

**Docker (producción):**
```bash
make build      # construye imagen (pip install . desde pyproject)
make up         # levanta en background en puerto 8001
make logs       # ver logs
make restart    # tras git pull + make build
make migrate    # one-shot legacy: migra una DB single-tenant vieja al esquema multi-tenant
make migrate-db # aplica las migraciones Alembic (alembic upgrade head) a la DB local
```
El `CMD` del contenedor corre `alembic upgrade head` antes de arrancar uvicorn
(no-op si la DB ya está en head).

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
- `DATABASE_URL` (default `sqlite:///./sanez.db`), `UPLOAD_DIR` (default `static/uploads`), `UPLOAD_MAX_BYTES` (default 5 MB).
- `SCHEDULER_ENABLED` (default 1), `SCHEDULER_HOUR`/`SCHEDULER_MINUTE` (14:00) y `SCHEDULER_TZ` (`America/Caracas`).

Todas se definen en `app/config.py` (`Settings`).

**Protección CSRF:** dependencia global `verify_csrf` valida un token de sesión
(`csrf_token`) en toda petición mutante. Las plantillas lo reciben vía
`context_processor`; cada `<form method="post">` debe incluir
`<input type="hidden" name="csrf_token" value="{{ csrf_token }}">`.

## Architecture

Es **multi-tenant** desde la v1: un super-admin da de alta cuentas; cada
usuario gestiona sus categorías, productos y backgrounds; el público consume
`/menu/<slug>`. El código está organizado en un paquete `app/` por capas; el
entrypoint sigue siendo `uvicorn main:app` (`main.py` solo llama a
`app.factory.create_app()`).

**Estructura del paquete `app/`:**
- **`config.py`** — `Settings` (pydantic-settings) que mapea todas las env vars + `get_settings()` cacheado. Hace **fail-hard** si falta `SECRET_KEY` (salvo `DEV_MODE`). Toda lectura de entorno pasa por acá (nada de `os.environ` disperso).
- **`factory.py`** — `create_app()`: arma la `FastAPI`, registra `SessionMiddleware`, la dependencia global `verify_csrf`, monta `/static`, incluye los routers y usa un `lifespan` (reemplaza `@app.on_event`) que crea tablas, bootstrapea el super-admin y arranca/para el scheduler. El rate limiter de login vive en `app.state.login_limiter` (una instancia por app).
- **`db.py`** — `engine`, `SessionLocal`, dependencia `get_db`, helper `create_all()`. **`models/`** — un modelo por archivo (`user`, `category`, `item`, `exchange_rate`) + `base.Base`; `models/__init__.py` los re-exporta.
- **`security/`** — `passwords.py` (bcrypt, truncado a 72 bytes), `csrf.py` (`verify_csrf`, `get_csrf_token`), `rate_limit.py` (`LoginRateLimiter`).
- **`dependencies.py`** — `current_user`, `require_user`, `require_super_admin` + la excepción `RedirectToLogin` y su handler (redirige a `/login`).
- **`services/`** — **toda la lógica de negocio**, sin tocar HTTP. Reciben una `Session` y valores planos; lanzan `ServiceError(message)` en validaciones. `menu` (paginación de pantallas + backgrounds), `category` (CRUD + reorden con renumber contiguo), `item`, `user` (slug, `user_stats` con counts agrupados, CRUD), `upload`, `rates`.
- **`routers/`** — handlers finos que parsean forms, llaman services, traducen `ServiceError` a `back_to(error=...)` y renderizan plantillas. `public.py` (`/`, login/logout, `/menu/{slug}`, `/api/data/{slug}`, `/api/exchange-rates`), `admin.py` (`require_user`: `/admin`, settings, CRUD categorías/items, stop-impersonating), `superadmin.py` (`require_super_admin`: `/super`, CRUD usuarios, impersonate). `helpers.back_to` es el redirect con query params.
- **`bootstrap.py`** — `init_db(settings)`: **solo** seed idempotente del super-admin (el esquema lo crea `create_all`/Alembic).
- **`scheduler.py`** — `build_scheduler(settings)`; se construye dentro de `create_app` (sin side-effects al importar).

**Migraciones (Alembic):** `migrations/` con `env.py` que lee la URL de `Settings`
y usa `Base.metadata`. La DB existente quedó *stampeada* en la baseline. Para
cambios de esquema: `alembic revision --autogenerate -m "..."` → `alembic upgrade head`
(o `make migrate-db`). El lifespan también llama `create_all()` como red de
seguridad para dev local.

**Tests:** `tests/` con pytest. `conftest.py` usa un engine SQLite in-memory
(`StaticPool`) compartido y overridea `get_db`; el scheduler se apaga con
`SCHEDULER_ENABLED=0`. Hay helpers para el flujo CSRF (`tests/helpers.py`).

**Modelos:**
- `User` (id, email, slug único, nombre_negocio, password_hash, is_active, is_super_admin, tiempo_rotacion_segundos).
- `Category` (id, user_id, nombre, orden, background_path). UniqueConstraint(user_id, orden).
- `ProductItem` (id, category_id, nombre, precio: **String** — no Float; el frontend lo muestra tal cual).
- `ExchangeRate` (currency PK: `"USD"` | `"EUR"`, rate: Float, updated_at). Una fila por moneda; se sobreescribe en cada ejecución del scraper.

**Slug:** validado en `app/services/user.py` por `SLUG_REGEX` (`^[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?$`) + `RESERVED_SLUGS` (`admin`, `super`, `api`, `login`, `logout`, `static`, `menu`).

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
`capa_idx` es el índice posicional de la categoría en su orden, y `backgrounds[capa_idx]` es su imagen (puede ser `null`). Una categoría con >~15 items se parte en varias `pantallas` (mismo `capa_idx`) vía `app/services/menu.py::split_items_into_screens` (reparto equilibrado con `ceil(n/15)` pantallas).

**Frontend (`templates/public.html`)** es un único HTML autocontenido sin build. Lee `data-slug` del `<body>`, fetchea `/api/data/{slug}` al cargar y silenciosamente cada 30 s, y crea los `bg-capa` divs **dinámicamente** según `backgrounds.length` (cualquier cantidad de categorías, no más 4 fijos). Cycla por `pantallas[]` con crossfades CSS: el background sólo transiciona cuando `capa_idx` cambia entre pantallas consecutivas.

**Admin** (`/admin`, `templates/admin/dashboard.html`) usa Jinja2 + form POSTs, sin framework JS. Itera sobre `user.categorias` (dinámico). El super-admin (`templates/super/users_list.html`, `templates/super/user_form.html`) sigue el mismo patrón.

**Uploads:** se almacenan en `static/uploads/<user_id>/cat_<category_id>.<ext>`. Al borrar la categoría se borra el archivo; al borrar el usuario, se borra su carpeta entera con `shutil.rmtree`. El volumen `./static/uploads` montado en Docker cubre toda la jerarquía.

**Migración legacy → multi-tenant:** `scripts/migrate_to_multitenant.py` detecta el esquema viejo (tabla `categories` con PK `clave`), lee la data con SQL crudo, dropea las tablas viejas, crea el esquema nuevo y reinjecta todo bajo un usuario "legacy" (`LEGACY_SLUG`, default `demo`). Es idempotente.

**Scraper BCV (`scrapers/`):**
- `scrapers/bcv.py` — `fetch_bcv_rates()` hace GET a `https://www.bcv.org.ve/`, parsea los bloques `#dolar` y `#euro` con BeautifulSoup y devuelve `{"USD": float, "EUR": float}`. Usa `verify=False` porque BCV tiene un certificado de CA gubernamental venezolana que no está en el trust store estándar.
- `scrapers/tasks.py` — `fetch_and_save_rates()` llama al scraper y hace upsert en `exchange_rates`. Es la función que ejecuta el scheduler.
- El scheduler se arma en `app/scheduler.py::build_scheduler(settings)` (`APScheduler BackgroundScheduler`, tz `SCHEDULER_TZ` default `America/Caracas`) y dispara `fetch_and_save_rates` cada día a las **14:00 VET** (`SCHEDULER_HOUR`/`SCHEDULER_MINUTE`). El `lifespan` de `create_app` lo arranca/detiene; se puede apagar con `SCHEDULER_ENABLED=0` (los tests lo usan).
- Endpoint público de consulta: `GET /api/exchange-rates` → `{"USD": {"rate": ..., "updated_at": ...}, "EUR": {...}}`.
- Para consumir las tasas desde cualquier otra función: `db.get(ExchangeRate, "USD")` / `db.get(ExchangeRate, "EUR")`.
