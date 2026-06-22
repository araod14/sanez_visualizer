# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Dev local** (requires Python 3.12+):
```bash
python3 -m venv venv && source venv/bin/activate
make install            # pip install -e ".[dev]"  (deps + pytest/ruff)
make dev                # DEV_MODE=1 uvicorn con reload (ver comando exacto abajo)
```

O directamente sin Make:
```bash
DEV_MODE=1 SUPER_ADMIN_EMAIL=admin@local SUPER_ADMIN_PASSWORD=admin \
  venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

`DEV_MODE=1` permite arrancar sin `SECRET_KEY` (genera una clave efímera) y
desactiva el flag `Secure` de la cookie de sesión para poder usar HTTP local.
Las dependencias y la config de herramientas (ruff, pytest) viven en
`pyproject.toml` (ya no hay `requirements.txt`).

**Tests / calidad:**
```bash
make test                 # Todos los tests (pytest con engine in-memory)
make test -- -k "test_"  # Filtrar por pattern (ej: "test_login")
make test -v             # Verbose
make lint                 # ruff check + ruff format --check
make lint -- --fix       # Aplicar fixes automáticos
```
Los tests usan SQLite in-memory (`conftest.py` con `StaticPool`) y **no tocan la DB real**.

**Docker (producción):**
```bash
make build      # construye imagen (pip install . desde pyproject)
make up         # levanta en background en puerto 8001 (mapeado desde 8000 interno)
make down       # detiene el contenedor
make logs       # tail de logs en vivo
make restart    # down + up
make ps         # docker compose ps
make migrate    # one-shot legacy: migra una DB single-tenant vieja al esquema multi-tenant
make migrate-db # aplica las migraciones Alembic (alembic upgrade head) a la DB local
```
El `CMD` del contenedor corre `alembic upgrade head` antes de arrancar uvicorn
(no-op si la DB ya está en head). Ver `Dockerfile` y `docker-compose.yml` para
volumens y variables.

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
- `IMAGE_PROVIDER` (default `gemini`), `IMAGE_API_KEY` (vacío por defecto), `IMAGE_MODEL`
  (default `gemini-2.5-flash-image`), `IMAGE_ASPECT_RATIO` (default `16:9`) — generación de
  fondos por IA. Con `gemini` se necesita `IMAGE_API_KEY` **y billing habilitado** (todos los
  modelos de imagen de Gemini tienen `limit: 0` en free tier). Sin `IMAGE_API_KEY` la opción
  sigue visible pero generar devuelve un error de configuración. Alternativa **gratis y sin
  clave** para pruebas: `IMAGE_PROVIDER=pollinations` (image.pollinations.ai, GET sin auth;
  ignora `IMAGE_API_KEY`/`IMAGE_MODEL`, usa `IMAGE_ASPECT_RATIO` para las dimensiones).

Todas se definen en `app/config.py` (`Settings`).

**Protección CSRF:** dependencia global `verify_csrf` valida un token de sesión
(`csrf_token`) en toda petición mutante (POST/PUT/DELETE). Las plantillas lo reciben
vía `render_template()` en `templates.py`; cada `<form method="post">` debe incluir
`<input type="hidden" name="csrf_token" value="{{ csrf_token }}">`. Los tests de POST
en `conftest.py` incluyen un helper para fetchear el token antes de mutar.

## Architecture

Es **multi-tenant** desde la v1: un super-admin da de alta cuentas; cada
usuario gestiona sus categorías, productos y backgrounds; el público consume
`/menu/<slug>`. El código está organizado en un paquete `app/` por capas; el
entrypoint sigue siendo `uvicorn main:app` (`main.py` solo llama a
`app.factory.create_app()`).

**Estructura del paquete `app/`:**
- **`config.py`** — `Settings` (pydantic-settings) que mapea todas las env vars + `get_settings()` cacheado. Hace **fail-hard** si falta `SECRET_KEY` (salvo `DEV_MODE`). Toda lectura de entorno pasa por acá (nada de `os.environ` disperso).
- **`factory.py`** — `create_app()`: arma la `FastAPI`, registra `SessionMiddleware`, la dependencia global `verify_csrf`, monta `/static`, incluye los routers y usa un `lifespan` (reemplaza `@app.on_event`) que crea tablas, bootstrapea el super-admin y arranca/para el scheduler. El rate limiter de login vive en `app.state.login_limiter` (una instancia por app).
- **`db.py`** — `engine`, `SessionLocal`, dependencia `get_db`, helper `create_all()`. 
- **`models/`** — un modelo por archivo (`user`, `category`, `item`, `exchange_rate`) + `base.Base`; `models/__init__.py` los re-exporta.
- **`security/`** — `passwords.py` (bcrypt, truncado a 72 bytes), `csrf.py` (`verify_csrf`, `get_csrf_token`), `rate_limit.py` (`LoginRateLimiter`).
- **`dependencies.py`** — `current_user`, `require_user`, `require_super_admin` + la excepción `RedirectToLogin` y su handler (redirige a `/login`).
- **`services/`** — **toda la lógica de negocio**, sin tocar HTTP. Reciben una `Session` y valores planos; lanzan `ServiceError(message)` en validaciones. `menu` (paginación de pantallas + backgrounds), `category` (CRUD + reorden con renumber contiguo), `item`, `user` (slug, `user_stats` con counts agrupados, CRUD), `upload`, `rates`.
- **`routers/`** — handlers finos que parsean forms, llaman services, traducen `ServiceError` a `back_to(error=...)` y renderizan plantillas. `public.py` (`/`, login/logout, `/menu/{slug}`, `/api/data/{slug}`, `/api/exchange-rates`), `admin.py` (`require_user`: `/admin`, settings, CRUD categorías/items, stop-impersonating), `superadmin.py` (`require_super_admin`: `/super`, CRUD usuarios, impersonate). Cada router usa `helpers.back_to(url, error=...)` para redirects con flash messages.
- **`bootstrap.py`** — `init_db(settings)`: **solo** seed idempotente del super-admin (el esquema lo crea `create_all`/Alembic).
- **`templates.py`** — helper `render_template(request, name, **context)` que inyecta `request`, `csrf_token`, `user` (si autenticado) y `flash` en todas las plantillas Jinja2.
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
- `User` (id, email, slug único, nombre_negocio, password_hash, is_active, is_super_admin, tiempo_rotacion_segundos, `estilo_lista`).
- `Category` (id, user_id, nombre, orden, background_path). UniqueConstraint(user_id, orden).
- `ProductItem` (id, category_id, nombre, precio: **String** — no Float; el frontend lo muestra tal cual; `descripcion`, `precio_peq`, `precio_med`, `precio_gran` — todos nullable, usados por el estilo pizzería).
- `ExchangeRate` (currency PK: `"USD"` | `"EUR"`, rate: Float, updated_at). Una fila por moneda; se sobreescribe en cada ejecución del scraper.

**Slug:** validado en `app/services/user.py` por `SLUG_REGEX` (`^[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?$`) + `RESERVED_SLUGS` (`admin`, `super`, `api`, `login`, `logout`, `static`, `menu`).

**`/api/data/{slug}` response shape:**
```json
{
  "tiempo_rotacion": 10,
  "estilo_lista": "estilo_1",
  "backgrounds": ["/static/uploads/<user_id>/cat_<id>.jpg", null, ...],
  "pantallas": [
    {"capa_idx": 0, "categoria_nombre": "Cervezas", "precio_modo": "ambos",
     "items": [{"id": 1, "nombre": "Polar", "precio": "2", "precio_bss": "Bs 72,00",
                "descripcion": "", "tamanos": []}]}
  ]
}
```
`descripcion` es string (puede ser `""`). `tamanos` es lista (vacía si el item no tiene
precios por tamaño); cada elemento `{"etiqueta": "Peq."|"Med."|"Gran.", "precio": <str>,
"precio_bss": <str|null>}`.
`capa_idx` es el índice posicional de la categoría en su orden, y `backgrounds[capa_idx]` es su imagen (puede ser `null`). Una categoría con >~15 items se parte en varias `pantallas` (mismo `capa_idx`) vía `app/services/menu.py::split_items_into_screens` (reparto equilibrado con `ceil(n/15)` pantallas).

**Modo de precio (`Category.precio_modo`):** cada categoría elige cómo se publica el precio: `usd_fijo` (precio fijo en `$`), `bss_fijo` (precio fijo en `Bs`), `usd_a_bss` (el precio se carga en dólares y se convierte a Bs con la tasa `USD` guardada) o `ambos` (`$` + conversión). La conversión y el formateo `Bs 1.625,00` se hacen **en el servidor** en `app/services/menu.py` (`parse_price`, `format_bss`, `compute_precio_bss`); `build_menu_payload(user, usd_rate)` recibe la tasa USD (leída en `public.py::api_data` vía `db.get(ExchangeRate, "USD")`) y agrega `precio_modo` por pantalla y `precio_bss` por item (string ya formateado o `null` si no aplica / precio no numérico). Se edita por categoría en `/admin` (`POST /admin/categories/{id}/price-mode` → `category_service.set_price_mode`).

**Estilo de cartelera (`User.estilo_lista`):** cada usuario elige **uno** de 5 estilos visuales para toda su cartelera (`estilo_1` clásico, `estilo_2` tarjetas oscuras, `estilo_3` pizzería, `estilo_4` neón, `estilo_5` minimalista). Validado en `app/services/menu.py::LIST_STYLES` (default `estilo_1`). Se edita en `/admin` (`POST /admin/style` → `user_service.set_estilo_lista`) con un grupo de botones; se sirve en la raíz del payload (`estilo_lista`) y el frontend lo aplica como clase en `#overlay`. El estilo pizzería usa `descripcion` y `tamanos` por item; el resto solo `precio`/`precio_bss`.

**Frontend (`templates/public.html`)** es un único HTML autocontenido sin build. Lee `data-slug` del `<body>`, fetchea `/api/data/{slug}` al cargar y silenciosamente cada 30 s, y crea los `bg-capa` divs **dinámicamente** según `backgrounds.length` (cualquier cantidad de categorías, no más 4 fijos). Cycla por `pantallas[]` con crossfades CSS: el background sólo transiciona cuando `capa_idx` cambia entre pantallas consecutivas. El render de items se despacha por estilo vía el objeto `GENERADORES[estilo]` (uno por `estilo_N`); `precioInfo(it, modo)` centraliza la lógica de `$`/`Bs` respetando `precio_modo`.

**Admin UI:** `/admin` (`templates/admin/dashboard.html`) usa Jinja2 + form POSTs, sin framework JS. Itera sobre `user.categorias` (dinámico). El super-admin (`templates/super/users_list.html`, `templates/super/user_form.html`) sigue el mismo patrón. Flash messages se renderizan con `{{ flash }}` si existe en el context.

**Patrón de error en routers:** Los handlers atrapan `ServiceError` y redirigen con `back_to(request.url, error=str(e))`, que serializa el mensaje en la query string y lo renderiza en la plantilla como alert visual. Ej:
```python
try:
    service.do_something(db, user_id, data)
except ServiceError as e:
    return back_to(request.url, error=str(e))
```

**Uploads:** se almacenan en `static/uploads/<user_id>/cat_<category_id>.<ext>`. Al borrar la categoría se borra el archivo; al borrar el usuario, se borra su carpeta entera con `shutil.rmtree`. El volumen `./static/uploads` montado en Docker cubre toda la jerarquía.

**Fondos generados por IA (texto → imagen):** alternativa a subir un archivo. El usuario
escribe una palabra/frase y un proveedor de IA (`app/services/image_gen.py`,
`generate_background_image` — intercambiable por `IMAGE_PROVIDER`, arranca con Google Gemini
vía `requests`) genera una imagen de fondo. `build_prompt` envuelve la frase con un
`BASE_PROMPT` de "buen gusto" (landscape, sin texto, tonos que no compiten con el menú).
Flujo **previsualizar y confirmar** sin estado en DB: la generación guarda un PNG efímero
determinístico `static/uploads/<user_id>/cat_<id>__preview.png` (helpers en
`services/upload.py`: `save_category_preview`/`read_category_preview`/
`delete_category_preview`/`category_preview_path`). Endpoints en `admin.py`:
`POST /admin/categories/{id}/background/generate` (genera → redirige a
`/admin?preview=<id>&prompt=<frase>#cat-<id>`), `.../background/confirm`
(`category_service.confirm_generated_background` promueve el preview a fondo definitivo vía
`save_category_image` y borra el preview) y `.../background/discard` (borra el preview).
`admin_panel` lee `?preview`/`?prompt` y expone `c.preview_url`/`c.preview_prompt` al template
(bloque con Guardar/Regenerar/Descartar en `templates/admin/dashboard.html`). `delete_category`
borra también el preview huérfano. **Nota:** `resolve_background` y `delete_file_if_exists`
usan el path tal cual (sin `lstrip("/")` para el filesystem), por lo que funcionan con
`UPLOAD_DIR` relativo (producción) o absoluto (tests con `tmp_path`).

**Migración legacy → multi-tenant:** `scripts/migrate_to_multitenant.py` detecta el esquema viejo (tabla `categories` con PK `clave`), lee la data con SQL crudo, dropea las tablas viejas, crea el esquema nuevo y reinjecta todo bajo un usuario "legacy" (`LEGACY_SLUG`, default `demo`). Es idempotente.

**Scraper BCV (`scrapers/`):**
- `scrapers/bcv.py` — `fetch_bcv_rates()` hace GET a `https://www.bcv.org.ve/`, parsea los bloques `#dolar` y `#euro` con BeautifulSoup y devuelve `{"USD": float, "EUR": float}`. Usa `verify=False` porque BCV tiene un certificado de CA gubernamental venezolana que no está en el trust store estándar.
- `scrapers/tasks.py` — `fetch_and_save_rates()` llama al scraper y hace upsert en `exchange_rates`. Es la función que ejecuta el scheduler.
- El scheduler se arma en `app/scheduler.py::build_scheduler(settings)` (`APScheduler BackgroundScheduler`, tz `SCHEDULER_TZ` default `America/Caracas`) y dispara `fetch_and_save_rates` cada día a las **14:00 VET** (`SCHEDULER_HOUR`/`SCHEDULER_MINUTE`). El `lifespan` de `create_app` lo arranca/detiene; se puede apagar con `SCHEDULER_ENABLED=0` (los tests lo usan).
- Endpoint público de consulta: `GET /api/exchange-rates` → `{"USD": {"rate": ..., "updated_at": ...}, "EUR": {...}}`.
- Para consumir las tasas desde cualquier otra función: `db.get(ExchangeRate, "USD")` / `db.get(ExchangeRate, "EUR")`.

## Patrones y convenciones

**Transacciones / DB:** Cada request recibe una `Session` via `get_db` (dependency). Se auto-rollback en excepción; no uses `session.commit()` directamente. SQLAlchemy 2.0 maneja implicit flushes automáticamente.

**Validaciones:** Toda validación **debe** estar en `services/`, no en routers. Si la validación falla, lanza `ServiceError(message)` (importar de `app.services`). El router la atrapa y usa `back_to(request.url, error=...)`.

**Slugs:** Cuando crées/modifiques un usuario, valida el slug usando `user_service.validate_slug(slug)` (levanta `ServiceError` si inválido o reserved).

**Precios:** El campo `ProductItem.precio` es String, no Float. Parseo/formateo en `services/menu.py`. Si agregás lógica de precio, **nunca uses float** en la DB para evitar redondeos.

**Uploads:** Los paths se normalizan con `pathlib.Path()` y validados en `services/upload.py`. Los archivos se guardan **nunicamente** si `Category` o `User` existe en DB. Al borrar, se borra el archivo local también (con `pathlib.unlink()`).

**Migraciones:** Después de cambiar los modelos, corre `alembic revision --autogenerate -m "..."` y verifica el `.py` generado. Para rollback: `alembic downgrade -1`. En dev local, `make migrate-db` es equivalente a `alembic upgrade head`.

**Tests:** Importa desde `tests/conftest.py` el client (TestClient) y helpers (ej: `csrf_token_from(response)`). La DB en-memory se resetea entre tests automáticamente.
