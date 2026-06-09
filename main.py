import math
import os
import re
import secrets
import shutil
import time
from collections import defaultdict
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from database import (
    Category,
    ProductItem,
    User,
    get_db,
    hash_password,
    init_db,
    verify_password,
)

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
def _env_bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


# DEV_MODE habilita atajos inseguros (clave de sesión efímera) para desarrollo local.
DEV_MODE = _env_bool("DEV_MODE", False)

SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    if DEV_MODE:
        SECRET_KEY = secrets.token_hex(32)
        print("ADVERTENCIA: SECRET_KEY no configurada (DEV_MODE). Clave temporal — las sesiones no persistirán entre reinicios.")
    else:
        raise RuntimeError(
            "SECRET_KEY no configurada. Define SECRET_KEY en el entorno "
            "(o DEV_MODE=1 para desarrollo local con clave efímera)."
        )

# Cookie de sesión: en producción debe servirse sobre HTTPS (SESSION_HTTPS_ONLY=1, por defecto fuera de DEV_MODE).
SESSION_HTTPS_ONLY = _env_bool("SESSION_HTTPS_ONLY", not DEV_MODE)
SESSION_SAME_SITE = os.environ.get("SESSION_SAME_SITE", "lax").strip().lower()

# Rate limiting de login: ventana deslizante en memoria por IP (por proceso).
LOGIN_MAX_ATTEMPTS = int(os.environ.get("LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_WINDOW_SECONDS = int(os.environ.get("LOGIN_WINDOW_SECONDS", "300"))
_login_attempts: dict[str, list[float]] = defaultdict(list)

UPLOAD_DIR = Path("static/uploads")
EXTENSIONES_PERMITIDAS = {".jpg", ".jpeg", ".png", ".webp"}
TAMANO_MAXIMO = 5 * 1024 * 1024  # 5 MB

SLUG_REGEX = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?$")
RESERVED_SLUGS = {"admin", "super", "api", "login", "logout", "static", "menu", ""}

CSRF_FIELD = "csrf_token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def get_csrf_token(request: Request) -> str:
    """Devuelve (creando si hace falta) el token CSRF de la sesión actual."""
    token = request.session.get(CSRF_FIELD)
    if not token:
        token = secrets.token_urlsafe(32)
        request.session[CSRF_FIELD] = token
    return token


async def verify_csrf(request: Request) -> None:
    """Dependencia global: valida el token CSRF en toda petición mutante (form POST)."""
    if request.method in SAFE_METHODS:
        return
    form = await request.form()
    sent = form.get(CSRF_FIELD)
    expected = request.session.get(CSRF_FIELD)
    if not expected or not isinstance(sent, str) or not secrets.compare_digest(sent, expected):
        raise HTTPException(
            status_code=403,
            detail="Token CSRF inválido o ausente. Recarga la página e inténtalo de nuevo.",
        )

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Visual Panel", dependencies=[Depends(verify_csrf)])
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    https_only=SESSION_HTTPS_ONLY,
    same_site=SESSION_SAME_SITE,
)
app.mount("/static", StaticFiles(directory="static"), name="static")

# El context_processor inyecta `csrf_token` en todas las plantillas automáticamente.
templates = Jinja2Templates(
    directory="templates",
    context_processors=[lambda request: {"csrf_token": get_csrf_token(request)}],
)


@app.on_event("startup")
def startup():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    init_db()


# ---------------------------------------------------------------------------
# Autenticación
# ---------------------------------------------------------------------------
class _RedirectToLogin(Exception):
    pass


@app.exception_handler(_RedirectToLogin)
async def redirect_to_login(request: Request, exc: _RedirectToLogin):
    return RedirectResponse(url="/login", status_code=302)


def current_user(request: Request, db: Session) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = db.get(User, user_id)
    if not user or not user.is_active:
        return None
    return user


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = current_user(request, db)
    if not user:
        raise _RedirectToLogin()
    return user


def require_super_admin(request: Request, db: Session = Depends(get_db)) -> User:
    user = current_user(request, db)
    if not user or not user.is_super_admin:
        raise _RedirectToLogin()
    return user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def validar_slug(slug: str) -> str | None:
    slug = (slug or "").strip().lower()
    if slug in RESERVED_SLUGS:
        return None
    if not SLUG_REGEX.match(slug):
        return None
    return slug


def user_upload_dir(user_id: int) -> Path:
    d = UPLOAD_DIR / str(user_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def borrar_archivo_si_existe(ruta_relativa: str | None) -> None:
    if not ruta_relativa:
        return
    p = Path(ruta_relativa.lstrip("/"))
    if p.exists() and p.is_file():
        try:
            p.unlink()
        except OSError:
            pass


def back_to(url: str, *, ok: str = "", error: str = "") -> RedirectResponse:
    from urllib.parse import urlencode
    qs = urlencode({k: v for k, v in {"ok": ok, "error": error}.items() if v})
    sep = "&" if "?" in url else "?"
    return RedirectResponse(url=f"{url}{sep}{qs}" if qs else url, status_code=302)


# ---------------------------------------------------------------------------
# Login / logout
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def root(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if user:
        return RedirectResponse(url="/super" if user.is_super_admin else "/admin", status_code=302)
    return RedirectResponse(url="/login", status_code=302)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    return templates.TemplateResponse(request, "login.html", {"error": error})


@app.post("/login")
async def login_submit(
    request: Request,
    db: Session = Depends(get_db),
    usuario: str = Form(...),
    contrasena: str = Form(...),
):
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    recientes = [t for t in _login_attempts[ip] if now - t < LOGIN_WINDOW_SECONDS]
    _login_attempts[ip] = recientes
    if len(recientes) >= LOGIN_MAX_ATTEMPTS:
        return templates.TemplateResponse(
            request, "login.html",
            {"error": "Demasiados intentos fallidos. Espera unos minutos e inténtalo de nuevo."},
            status_code=429,
        )

    user = db.query(User).filter(User.email == usuario.strip().lower()).first()
    if not user or not user.is_active or not verify_password(contrasena, user.password_hash):
        _login_attempts[ip].append(now)
        return templates.TemplateResponse(
            request, "login.html",
            {"error": "Usuario o contraseña incorrectos."},
            status_code=401,
        )
    _login_attempts.pop(ip, None)
    request.session.clear()
    request.session["user_id"] = user.id
    return RedirectResponse(url="/super" if user.is_super_admin else "/admin", status_code=302)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


# ---------------------------------------------------------------------------
# Pantalla pública
# ---------------------------------------------------------------------------
@app.get("/menu/{slug}", response_class=HTMLResponse)
async def pantalla_publica(request: Request, slug: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.slug == slug, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Menú no encontrado")
    return templates.TemplateResponse(request, "public.html", {"slug": slug, "nombre_negocio": user.nombre_negocio})


@app.get("/api/data/{slug}")
async def api_data(slug: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.slug == slug, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Menú no encontrado")

    cats = sorted(user.categorias, key=lambda c: c.orden)

    backgrounds = []
    for c in cats:
        if c.background_path and Path(c.background_path.lstrip("/")).exists():
            backgrounds.append(f"/{c.background_path.lstrip('/')}")
        else:
            backgrounds.append(None)

    pantallas = []
    for capa_idx, cat in enumerate(cats):
        items = [
            {"id": it.id, "nombre": it.nombre, "precio": it.precio}
            for it in cat.items
        ]
        n = len(items)
        num_screens = max(1, math.ceil(n / 15)) if n > 0 else 1
        base, remainder = n // num_screens, n % num_screens
        start = 0
        for i in range(num_screens):
            size = base + (1 if i < remainder else 0)
            pantallas.append({
                "capa_idx": capa_idx,
                "categoria_nombre": cat.nombre,
                "items": items[start:start + size],
            })
            start += size

    return JSONResponse({
        "tiempo_rotacion": user.tiempo_rotacion_segundos,
        "backgrounds": backgrounds,
        "pantallas": pantallas,
    })


# ---------------------------------------------------------------------------
# Panel de usuario
# ---------------------------------------------------------------------------
@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    ok: str = "",
    error: str = "",
):
    categorias = sorted(user.categorias, key=lambda c: c.orden)
    for c in categorias:
        c.background_url = (
            f"/{c.background_path.lstrip('/')}"
            if c.background_path and Path(c.background_path.lstrip("/")).exists()
            else None
        )
    impersonator_id = request.session.get("impersonator_id")
    return templates.TemplateResponse(request, "admin/dashboard.html", {
        "user": user,
        "categorias": categorias,
        "impersonating": bool(impersonator_id),
        "ok": ok,
        "error": error,
    })


@app.post("/admin/settings")
async def admin_settings(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    tiempo_rotacion: int = Form(...),
):
    if not (3 <= tiempo_rotacion <= 300):
        return back_to("/admin", error="El tiempo debe estar entre 3 y 300 segundos")
    user.tiempo_rotacion_segundos = tiempo_rotacion
    db.commit()
    return back_to("/admin", ok="Tiempo de rotación actualizado")


# ---------------------------------------------------------------------------
# Categorías (CRUD por usuario)
# ---------------------------------------------------------------------------
@app.post("/admin/categories")
async def admin_categoria_crear(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    nombre: str = Form(...),
):
    nombre = nombre.strip()
    if not nombre:
        return back_to("/admin", error="El nombre no puede estar vacío")
    if len(nombre) > 40:
        return back_to("/admin", error="Nombre demasiado largo (máx 40)")

    max_orden = db.query(Category).filter(Category.user_id == user.id).count()
    db.add(Category(user_id=user.id, nombre=nombre, orden=max_orden))
    db.commit()
    return back_to("/admin", ok=f"Categoría «{nombre}» creada")


def _get_owned_category(db: Session, cat_id: int, user: User) -> Category | None:
    cat = db.get(Category, cat_id)
    if not cat or cat.user_id != user.id:
        return None
    return cat


@app.post("/admin/categories/{cat_id}/edit")
async def admin_categoria_editar(
    request: Request,
    cat_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    nombre: str = Form(...),
):
    cat = _get_owned_category(db, cat_id, user)
    if not cat:
        return back_to("/admin", error="Categoría no encontrada")
    nombre = nombre.strip()
    if not nombre:
        return back_to("/admin", error="El nombre no puede estar vacío")
    cat.nombre = nombre[:40]
    db.commit()
    return back_to("/admin", ok="Categoría renombrada")


@app.post("/admin/categories/{cat_id}/move")
async def admin_categoria_mover(
    request: Request,
    cat_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    direccion: str = Form(...),
):
    cat = _get_owned_category(db, cat_id, user)
    if not cat:
        return back_to("/admin", error="Categoría no encontrada")
    if direccion not in {"arriba", "abajo"}:
        return back_to("/admin", error="Dirección inválida")

    ordenadas = sorted(user.categorias, key=lambda c: c.orden)
    idx = next((i for i, c in enumerate(ordenadas) if c.id == cat.id), -1)
    objetivo = idx - 1 if direccion == "arriba" else idx + 1
    if idx < 0 or objetivo < 0 or objetivo >= len(ordenadas):
        return back_to("/admin")

    # Reasignar ordenes contiguos para evitar choques con UniqueConstraint
    for i, c in enumerate(ordenadas):
        c.orden = -(i + 1)
    db.flush()
    ordenadas[idx], ordenadas[objetivo] = ordenadas[objetivo], ordenadas[idx]
    for i, c in enumerate(ordenadas):
        c.orden = i
    db.commit()
    return back_to("/admin")


@app.post("/admin/categories/{cat_id}/background")
async def admin_categoria_background(
    request: Request,
    cat_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    imagen: UploadFile = File(...),
):
    cat = _get_owned_category(db, cat_id, user)
    if not cat:
        return back_to("/admin", error="Categoría no encontrada")

    ext = Path(imagen.filename or "").suffix.lower()
    if ext not in EXTENSIONES_PERMITIDAS:
        return back_to("/admin", error="Formato no permitido (jpg/png/webp)")

    contenido = await imagen.read()
    if len(contenido) > TAMANO_MAXIMO:
        return back_to("/admin", error="Imagen demasiado grande (máx 5MB)")

    borrar_archivo_si_existe(cat.background_path)

    dest_dir = user_upload_dir(user.id)
    nombre_archivo = f"cat_{cat.id}{ext}"
    ruta_destino = dest_dir / nombre_archivo
    with open(ruta_destino, "wb") as f:
        f.write(contenido)

    cat.background_path = f"static/uploads/{user.id}/{nombre_archivo}"
    db.commit()
    return back_to("/admin", ok=f"Imagen de «{cat.nombre}» actualizada")


@app.post("/admin/categories/{cat_id}/delete")
async def admin_categoria_borrar(
    request: Request,
    cat_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    cat = _get_owned_category(db, cat_id, user)
    if not cat:
        return back_to("/admin", error="Categoría no encontrada")
    borrar_archivo_si_existe(cat.background_path)
    nombre = cat.nombre
    db.delete(cat)
    db.commit()

    # Reordenar los restantes para mantener orden contiguo
    restantes = sorted(
        db.query(Category).filter(Category.user_id == user.id).all(),
        key=lambda c: c.orden,
    )
    for i, c in enumerate(restantes):
        c.orden = -(i + 1)
    db.flush()
    for i, c in enumerate(restantes):
        c.orden = i
    db.commit()
    return back_to("/admin", ok=f"Categoría «{nombre}» eliminada")


# ---------------------------------------------------------------------------
# Items (productos)
# ---------------------------------------------------------------------------
def _get_owned_item(db: Session, item_id: int, user: User) -> ProductItem | None:
    item = db.get(ProductItem, item_id)
    if not item:
        return None
    if item.categoria.user_id != user.id:
        return None
    return item


@app.post("/admin/items/add")
async def admin_item_add(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    category_id: int = Form(...),
    nombre: str = Form(...),
    precio: str = Form(...),
):
    cat = _get_owned_category(db, category_id, user)
    if not cat:
        return back_to("/admin", error="Categoría inválida")

    nombre = nombre.strip()
    if not nombre:
        return back_to("/admin", error="El nombre del producto no puede estar vacío")
    precio = precio.strip()
    if not precio:
        return back_to("/admin", error="El precio no puede estar vacío")

    total = db.query(ProductItem).filter(ProductItem.category_id == cat.id).count()
    db.add(ProductItem(category_id=cat.id, nombre=nombre[:80], precio=precio[:30], orden=total))
    db.commit()
    return back_to("/admin", ok=f"Producto agregado a «{cat.nombre}»")


@app.post("/admin/items/{item_id}/edit")
async def admin_item_edit(
    request: Request,
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    nombre: str = Form(...),
    precio: str = Form(...),
):
    item = _get_owned_item(db, item_id, user)
    if not item:
        return back_to("/admin", error="Producto no encontrado")
    nombre = nombre.strip()
    precio = precio.strip()
    if not nombre:
        return back_to("/admin", error="El nombre no puede estar vacío")
    if not precio:
        return back_to("/admin", error="El precio no puede estar vacío")
    item.nombre = nombre[:80]
    item.precio = precio[:30]
    db.commit()
    return back_to("/admin", ok="Producto actualizado")


@app.post("/admin/items/{item_id}/delete")
async def admin_item_delete(
    request: Request,
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    item = _get_owned_item(db, item_id, user)
    if item:
        db.delete(item)
        db.commit()
    return back_to("/admin", ok="Producto eliminado")


# ---------------------------------------------------------------------------
# Super-admin
# ---------------------------------------------------------------------------
@app.get("/super", response_class=HTMLResponse)
async def super_panel(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_super_admin),
    ok: str = "",
    error: str = "",
):
    usuarios = db.query(User).order_by(User.is_super_admin.desc(), User.created_at.desc()).all()
    rows = []
    for u in usuarios:
        n_cats = db.query(Category).filter(Category.user_id == u.id).count()
        n_items = (
            db.query(ProductItem)
            .join(Category, ProductItem.category_id == Category.id)
            .filter(Category.user_id == u.id)
            .count()
        )
        rows.append({"u": u, "n_cats": n_cats, "n_items": n_items})
    return templates.TemplateResponse(request, "super/users_list.html", {
        "admin": admin,
        "rows": rows,
        "ok": ok,
        "error": error,
    })


@app.get("/super/users/new", response_class=HTMLResponse)
async def super_user_form(
    request: Request,
    admin: User = Depends(require_super_admin),
    error: str = "",
):
    return templates.TemplateResponse(request, "super/user_form.html", {
        "admin": admin,
        "modo": "crear",
        "target": None,
        "error": error,
    })


@app.post("/super/users")
async def super_user_create(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_super_admin),
    email: str = Form(...),
    slug: str = Form(...),
    nombre_negocio: str = Form(...),
    password: str = Form(...),
):
    email = email.strip().lower()
    nombre_negocio = nombre_negocio.strip()
    slug_v = validar_slug(slug)
    if not email or "@" not in email:
        return back_to("/super/users/new", error="Email inválido")
    if not slug_v:
        return back_to("/super/users/new", error="Slug inválido (solo letras/números/guion, no reservado)")
    if not nombre_negocio:
        return back_to("/super/users/new", error="Nombre del negocio requerido")
    if len(password) < 6:
        return back_to("/super/users/new", error="La contraseña debe tener al menos 6 caracteres")
    if db.query(User).filter(User.email == email).first():
        return back_to("/super/users/new", error="Email ya registrado")
    if db.query(User).filter(User.slug == slug_v).first():
        return back_to("/super/users/new", error="Slug ya en uso")

    nuevo = User(
        email=email,
        slug=slug_v,
        nombre_negocio=nombre_negocio[:80],
        password_hash=hash_password(password),
        is_active=True,
        is_super_admin=False,
    )
    db.add(nuevo)
    db.commit()
    return back_to("/super", ok=f"Usuario «{nombre_negocio}» creado (/menu/{slug_v})")


@app.get("/super/users/{user_id}/edit", response_class=HTMLResponse)
async def super_user_edit_form(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_super_admin),
    error: str = "",
):
    target = db.get(User, user_id)
    if not target:
        return back_to("/super", error="Usuario no encontrado")
    return templates.TemplateResponse(request, "super/user_form.html", {
        "admin": admin,
        "modo": "editar",
        "target": target,
        "error": error,
    })


@app.post("/super/users/{user_id}/edit")
async def super_user_edit(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_super_admin),
    email: str = Form(...),
    slug: str = Form(...),
    nombre_negocio: str = Form(...),
    is_active: str = Form(""),
    password: str = Form(""),
):
    target = db.get(User, user_id)
    if not target:
        return back_to("/super", error="Usuario no encontrado")

    email = email.strip().lower()
    nombre_negocio = nombre_negocio.strip()
    slug_v = validar_slug(slug)
    if not email or "@" not in email:
        return back_to(f"/super/users/{user_id}/edit", error="Email inválido")
    if not slug_v:
        return back_to(f"/super/users/{user_id}/edit", error="Slug inválido")
    if not nombre_negocio:
        return back_to(f"/super/users/{user_id}/edit", error="Nombre del negocio requerido")
    if db.query(User).filter(User.email == email, User.id != target.id).first():
        return back_to(f"/super/users/{user_id}/edit", error="Email ya registrado")
    if db.query(User).filter(User.slug == slug_v, User.id != target.id).first():
        return back_to(f"/super/users/{user_id}/edit", error="Slug ya en uso")

    target.email = email
    target.slug = slug_v
    target.nombre_negocio = nombre_negocio[:80]
    # No permitir desactivar al propio super-admin actual
    if target.id != admin.id:
        target.is_active = bool(is_active)
    if password:
        if len(password) < 6:
            return back_to(f"/super/users/{user_id}/edit", error="La contraseña debe tener al menos 6 caracteres")
        target.password_hash = hash_password(password)
    db.commit()
    return back_to("/super", ok="Usuario actualizado")


@app.post("/super/users/{user_id}/delete")
async def super_user_delete(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_super_admin),
):
    target = db.get(User, user_id)
    if not target:
        return back_to("/super", error="Usuario no encontrado")
    if target.id == admin.id:
        return back_to("/super", error="No puedes eliminar tu propia cuenta")
    if target.is_super_admin:
        return back_to("/super", error="No se puede eliminar otro super-admin desde aquí")

    # Borrar archivos del usuario en disco
    user_dir = UPLOAD_DIR / str(target.id)
    if user_dir.exists():
        shutil.rmtree(user_dir, ignore_errors=True)

    db.delete(target)
    db.commit()
    return back_to("/super", ok="Usuario eliminado")


@app.post("/super/users/{user_id}/impersonate")
async def super_user_impersonate(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_super_admin),
):
    target = db.get(User, user_id)
    if not target or not target.is_active:
        return back_to("/super", error="Usuario no disponible")
    if target.id == admin.id:
        return back_to("/super", error="Ya estás autenticado como ese usuario")
    request.session["impersonator_id"] = admin.id
    request.session["user_id"] = target.id
    return RedirectResponse(url="/admin", status_code=302)


@app.post("/admin/stop-impersonating")
async def stop_impersonating(request: Request, db: Session = Depends(get_db)):
    impersonator_id = request.session.get("impersonator_id")
    if not impersonator_id:
        return RedirectResponse(url="/admin", status_code=302)
    admin = db.get(User, impersonator_id)
    if not admin or not admin.is_super_admin:
        request.session.clear()
        return RedirectResponse(url="/login", status_code=302)
    request.session["user_id"] = admin.id
    request.session.pop("impersonator_id", None)
    return RedirectResponse(url="/super", status_code=302)
