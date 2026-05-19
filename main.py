import os
import secrets
from pathlib import Path

from fastapi import FastAPI, Request, Form, UploadFile, File, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from database import init_db, get_db, Settings, Background, Category, ProductItem

# ---------------------------------------------------------------------------
# Configuración desde variables de entorno
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get("SECRET_KEY", "")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")

if not SECRET_KEY:
    SECRET_KEY = secrets.token_hex(32)
    print("ADVERTENCIA: SECRET_KEY no configurada. Usando clave temporal — las sesiones no persistirán entre reinicios.")

if ADMIN_USER == "admin" and ADMIN_PASSWORD == "admin":
    print("ADVERTENCIA: Usando credenciales por defecto (admin/admin). Cambia ADMIN_USER y ADMIN_PASSWORD en producción.")

UPLOAD_DIR = Path("static/uploads")
EXTENSIONES_PERMITIDAS = {".jpg", ".jpeg", ".png", ".webp"}
TAMANO_MAXIMO = 5 * 1024 * 1024  # 5 MB

ORDEN_CATEGORIAS = ["ron", "whisky", "cerveza", "sangria"]

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Sanez Visualizer")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
def startup():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    init_db()


# ---------------------------------------------------------------------------
# Autenticación
# ---------------------------------------------------------------------------
def require_admin(request: Request):
    if not request.session.get("authenticated"):
        raise _RedirectToLogin()


class _RedirectToLogin(Exception):
    pass


@app.exception_handler(_RedirectToLogin)
async def redirect_to_login(request: Request, exc: _RedirectToLogin):
    return RedirectResponse(url="/admin/login", status_code=302)


@app.get("/admin/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    return templates.TemplateResponse(request, "login.html", {"error": error})


@app.post("/admin/login")
async def login_submit(
    request: Request,
    usuario: str = Form(...),
    contrasena: str = Form(...),
):
    if usuario == ADMIN_USER and contrasena == ADMIN_PASSWORD:
        request.session["authenticated"] = True
        return RedirectResponse(url="/admin", status_code=302)
    return templates.TemplateResponse(
        request, "login.html",
        {"error": "Usuario o contraseña incorrectos."},
        status_code=401,
    )


@app.get("/admin/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/admin/login", status_code=302)


# ---------------------------------------------------------------------------
# Pantalla pública
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def pantalla_publica(request: Request):
    return templates.TemplateResponse(request, "public.html")


@app.get("/api/data")
async def api_data(db: Session = Depends(get_db)):
    config = db.query(Settings).filter(Settings.id == 1).first()
    tiempo = config.tiempo_rotacion_segundos if config else 10

    fondos = db.query(Background).order_by(Background.orden).all()
    backgrounds = []
    for f in fondos:
        if f.ruta_archivo and Path(f.ruta_archivo.lstrip("/")).exists():
            backgrounds.append(f"/{f.ruta_archivo.lstrip('/')}")
        else:
            backgrounds.append(None)

    categorias = []
    for clave in ORDEN_CATEGORIAS:
        cat = db.query(Category).filter(Category.clave == clave).first()
        if cat:
            categorias.append({
                "clave": cat.clave,
                "nombre": cat.nombre,
                "items": [
                    {"id": it.id, "nombre": it.nombre, "precio": it.precio}
                    for it in cat.items
                ],
            })

    return JSONResponse({
        "tiempo_rotacion": tiempo,
        "backgrounds": backgrounds,
        "categorias": categorias,
    })


# ---------------------------------------------------------------------------
# Panel de administración
# ---------------------------------------------------------------------------
@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(
    request: Request,
    db: Session = Depends(get_db),
    ok: str = "",
    error: str = "",
):
    require_admin(request)
    config = db.query(Settings).filter(Settings.id == 1).first()

    fondos_info = []
    for f in db.query(Background).order_by(Background.orden).all():
        url = None
        if f.ruta_archivo and Path(f.ruta_archivo.lstrip("/")).exists():
            url = f"/{f.ruta_archivo.lstrip('/')}"
        fondos_info.append({"id": f.id, "url": url})

    categorias = []
    for clave in ORDEN_CATEGORIAS:
        cat = db.query(Category).filter(Category.clave == clave).first()
        if cat:
            categorias.append(cat)

    return templates.TemplateResponse(request, "admin.html", {
        "config": config,
        "fondos": fondos_info,
        "categorias": categorias,
        "ok": ok,
        "error": error,
    })


# ---------------------------------------------------------------------------
# Configuración: tiempo de rotación
# ---------------------------------------------------------------------------
@app.post("/admin/settings")
async def admin_settings(
    request: Request,
    db: Session = Depends(get_db),
    tiempo_rotacion: int = Form(...),
):
    require_admin(request)
    if not (3 <= tiempo_rotacion <= 300):
        return RedirectResponse(url="/admin?error=El+tiempo+debe+estar+entre+3+y+300+segundos", status_code=302)
    config = db.query(Settings).filter(Settings.id == 1).first()
    config.tiempo_rotacion_segundos = tiempo_rotacion
    db.commit()
    return RedirectResponse(url="/admin?ok=Tiempo+de+rotación+actualizado", status_code=302)


# ---------------------------------------------------------------------------
# Imágenes de fondo
# ---------------------------------------------------------------------------
@app.post("/admin/background")
async def admin_background(
    request: Request,
    db: Session = Depends(get_db),
    slot: int = Form(...),
    imagen: UploadFile = File(...),
):
    require_admin(request)

    if slot not in range(1, 5):
        return RedirectResponse(url="/admin?error=Ranura+inválida", status_code=302)

    ext = Path(imagen.filename).suffix.lower()
    if ext not in EXTENSIONES_PERMITIDAS:
        return RedirectResponse(url="/admin?error=Formato+no+permitido+(jpg/png/webp)", status_code=302)

    contenido = await imagen.read()
    if len(contenido) > TAMANO_MAXIMO:
        return RedirectResponse(url="/admin?error=Imagen+demasiado+grande+(máx+5MB)", status_code=302)

    fondo = db.query(Background).filter(Background.id == slot).first()
    if fondo.ruta_archivo:
        ruta_anterior = Path(fondo.ruta_archivo.lstrip("/"))
        if ruta_anterior.exists():
            ruta_anterior.unlink()

    nombre_archivo = f"bg_{slot}{ext}"
    ruta_destino = UPLOAD_DIR / nombre_archivo
    with open(ruta_destino, "wb") as f:
        f.write(contenido)

    fondo.ruta_archivo = f"static/uploads/{nombre_archivo}"
    db.commit()
    return RedirectResponse(url=f"/admin?ok=Imagen+{slot}+actualizada", status_code=302)


# ---------------------------------------------------------------------------
# Categorías: renombrar
# ---------------------------------------------------------------------------
@app.post("/admin/categories/{clave}")
async def admin_categoria_nombre(
    request: Request,
    clave: str,
    db: Session = Depends(get_db),
    nombre: str = Form(...),
):
    require_admin(request)
    if clave not in ORDEN_CATEGORIAS:
        return RedirectResponse(url="/admin?error=Categoría+inválida", status_code=302)
    nombre = nombre.strip()
    if not nombre:
        return RedirectResponse(url="/admin?error=El+nombre+no+puede+estar+vacío", status_code=302)
    cat = db.query(Category).filter(Category.clave == clave).first()
    cat.nombre = nombre
    db.commit()
    return RedirectResponse(url=f"/admin?ok=Nombre+de+categoría+actualizado", status_code=302)


# ---------------------------------------------------------------------------
# Items: agregar
# ---------------------------------------------------------------------------
@app.post("/admin/items/add")
async def admin_item_add(
    request: Request,
    db: Session = Depends(get_db),
    categoria_clave: str = Form(...),
    nombre: str = Form(...),
    precio: str = Form(...),
):
    require_admin(request)

    if categoria_clave not in ORDEN_CATEGORIAS:
        return RedirectResponse(url="/admin?error=Categoría+inválida", status_code=302)

    nombre = nombre.strip()
    if not nombre:
        return RedirectResponse(url="/admin?error=El+nombre+del+producto+no+puede+estar+vacío", status_code=302)

    try:
        precio_f = float(precio.strip())
        if precio_f < 0:
            raise ValueError
    except ValueError:
        return RedirectResponse(url="/admin?error=Precio+inválido", status_code=302)

    # Asignar orden al final de la lista
    total = db.query(ProductItem).filter(ProductItem.categoria_clave == categoria_clave).count()
    db.add(ProductItem(
        categoria_clave=categoria_clave,
        nombre=nombre,
        precio=precio_f,
        orden=total,
    ))
    db.commit()
    return RedirectResponse(url=f"/admin?ok=Producto+agregado+a+{categoria_clave}", status_code=302)


# ---------------------------------------------------------------------------
# Items: eliminar
# ---------------------------------------------------------------------------
@app.post("/admin/items/{item_id}/delete")
async def admin_item_delete(
    request: Request,
    item_id: int,
    db: Session = Depends(get_db),
):
    require_admin(request)
    item = db.query(ProductItem).filter(ProductItem.id == item_id).first()
    if item:
        db.delete(item)
        db.commit()
    return RedirectResponse(url="/admin?ok=Producto+eliminado", status_code=302)


# ---------------------------------------------------------------------------
# Items: editar
# ---------------------------------------------------------------------------
@app.post("/admin/items/{item_id}/edit")
async def admin_item_edit(
    request: Request,
    item_id: int,
    db: Session = Depends(get_db),
    nombre: str = Form(...),
    precio: str = Form(...),
):
    require_admin(request)

    nombre = nombre.strip()
    if not nombre:
        return RedirectResponse(url="/admin?error=El+nombre+no+puede+estar+vacío", status_code=302)

    try:
        precio_f = float(precio.strip())
        if precio_f < 0:
            raise ValueError
    except ValueError:
        return RedirectResponse(url="/admin?error=Precio+inválido", status_code=302)

    item = db.query(ProductItem).filter(ProductItem.id == item_id).first()
    if item:
        item.nombre = nombre
        item.precio = precio_f
        db.commit()
    return RedirectResponse(url="/admin?ok=Producto+actualizado", status_code=302)
