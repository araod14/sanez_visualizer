"""Rutas de usuario autenticado: panel, settings, CRUD de categorías e items."""

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import require_user
from app.models import User
from app.routers.helpers import back_to
from app.services import ServiceError
from app.services import category as category_service
from app.services import item as item_service
from app.services import user as user_service
from app.services.menu import resolve_background
from app.templates import templates

router = APIRouter()


@router.get("/admin", response_class=HTMLResponse)
async def admin_panel(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    ok: str = "",
    error: str = "",
):
    categorias = sorted(user.categorias, key=lambda c: c.orden)
    for c in categorias:
        c.background_url = resolve_background(c.background_path)
    impersonator_id = request.session.get("impersonator_id")
    return templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        {
            "user": user,
            "categorias": categorias,
            "impersonating": bool(impersonator_id),
            "ok": ok,
            "error": error,
        },
    )


@router.post("/admin/settings")
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


@router.post("/admin/style")
async def admin_estilo(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    estilo: str = Form(...),
):
    try:
        user_service.set_estilo_lista(db, user, estilo)
    except ServiceError as e:
        return back_to("/admin", error=e.message)
    return back_to("/admin", ok="Estilo de la cartelera actualizado")


@router.post("/admin/categories")
async def admin_categoria_crear(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    nombre: str = Form(...),
):
    try:
        nombre = category_service.create_category(db, user, nombre)
    except ServiceError as e:
        return back_to("/admin", error=e.message)
    return back_to("/admin", ok=f"Categoría «{nombre}» creada")


@router.post("/admin/categories/{cat_id}/edit")
async def admin_categoria_editar(
    request: Request,
    cat_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    nombre: str = Form(...),
):
    cat = category_service.get_owned_category(db, cat_id, user)
    if not cat:
        return back_to("/admin", error="Categoría no encontrada")
    try:
        category_service.rename_category(db, cat, nombre)
    except ServiceError as e:
        return back_to("/admin", error=e.message)
    return back_to("/admin", ok="Categoría renombrada")


@router.post("/admin/categories/{cat_id}/price-mode")
async def admin_categoria_modo_precio(
    request: Request,
    cat_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    modo: str = Form(...),
):
    cat = category_service.get_owned_category(db, cat_id, user)
    if not cat:
        return back_to("/admin", error="Categoría no encontrada")
    try:
        category_service.set_price_mode(db, cat, modo)
    except ServiceError as e:
        return back_to("/admin", error=e.message)
    return back_to("/admin", ok=f"Modo de precio de «{cat.nombre}» actualizado")


@router.post("/admin/categories/{cat_id}/move")
async def admin_categoria_mover(
    request: Request,
    cat_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    direccion: str = Form(...),
):
    cat = category_service.get_owned_category(db, cat_id, user)
    if not cat:
        return back_to("/admin", error="Categoría no encontrada")
    try:
        category_service.move_category(db, user, cat, direccion)
    except ServiceError as e:
        return back_to("/admin", error=e.message)
    return back_to("/admin")


@router.post("/admin/categories/{cat_id}/background")
async def admin_categoria_background(
    request: Request,
    cat_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    imagen: UploadFile = File(...),
):
    cat = category_service.get_owned_category(db, cat_id, user)
    if not cat:
        return back_to("/admin", error="Categoría no encontrada")
    contenido = await imagen.read()
    try:
        category_service.set_category_background(db, user, cat, imagen.filename or "", contenido)
    except ServiceError as e:
        return back_to("/admin", error=e.message)
    return back_to("/admin", ok=f"Imagen de «{cat.nombre}» actualizada")


@router.post("/admin/categories/{cat_id}/delete")
async def admin_categoria_borrar(
    request: Request,
    cat_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    cat = category_service.get_owned_category(db, cat_id, user)
    if not cat:
        return back_to("/admin", error="Categoría no encontrada")
    nombre = category_service.delete_category(db, user, cat)
    return back_to("/admin", ok=f"Categoría «{nombre}» eliminada")


@router.post("/admin/items/add")
async def admin_item_add(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    category_id: int = Form(...),
    nombre: str = Form(...),
    precio: str = Form(...),
    descripcion: str = Form(""),
    precio_peq: str = Form(""),
    precio_med: str = Form(""),
    precio_gran: str = Form(""),
):
    cat = category_service.get_owned_category(db, category_id, user)
    if not cat:
        return back_to("/admin", error="Categoría inválida")
    try:
        item_service.add_item(
            db, cat.id, nombre, precio, descripcion, precio_peq, precio_med, precio_gran
        )
    except ServiceError as e:
        return back_to("/admin", error=e.message)
    return back_to("/admin", ok=f"Producto agregado a «{cat.nombre}»")


@router.post("/admin/items/{item_id}/edit")
async def admin_item_edit(
    request: Request,
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    nombre: str = Form(...),
    precio: str = Form(...),
    descripcion: str = Form(""),
    precio_peq: str = Form(""),
    precio_med: str = Form(""),
    precio_gran: str = Form(""),
):
    item = item_service.get_owned_item(db, item_id, user)
    if not item:
        return back_to("/admin", error="Producto no encontrado")
    try:
        item_service.edit_item(
            db, item, nombre, precio, descripcion, precio_peq, precio_med, precio_gran
        )
    except ServiceError as e:
        return back_to("/admin", error=e.message)
    return back_to("/admin", ok="Producto actualizado")


@router.post("/admin/items/{item_id}/delete")
async def admin_item_delete(
    request: Request,
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    item = item_service.get_owned_item(db, item_id, user)
    if item:
        item_service.delete_item(db, item)
    return back_to("/admin", ok="Producto eliminado")


@router.post("/admin/stop-impersonating")
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
