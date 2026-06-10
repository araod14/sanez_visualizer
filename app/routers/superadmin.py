"""Rutas de super-admin: alta/baja/edición de usuarios e impersonación."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import require_super_admin
from app.models import User
from app.routers.helpers import back_to
from app.services import ServiceError
from app.services import user as user_service
from app.templates import templates

router = APIRouter()


@router.get("/super", response_class=HTMLResponse)
async def super_panel(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_super_admin),
    ok: str = "",
    error: str = "",
):
    rows = user_service.user_stats(db)
    return templates.TemplateResponse(
        request,
        "super/users_list.html",
        {"admin": admin, "rows": rows, "ok": ok, "error": error},
    )


@router.get("/super/users/new", response_class=HTMLResponse)
async def super_user_form(
    request: Request,
    admin: User = Depends(require_super_admin),
    error: str = "",
):
    return templates.TemplateResponse(
        request,
        "super/user_form.html",
        {"admin": admin, "modo": "crear", "target": None, "error": error},
    )


@router.post("/super/users")
async def super_user_create(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_super_admin),
    email: str = Form(...),
    slug: str = Form(...),
    nombre_negocio: str = Form(...),
    password: str = Form(...),
):
    try:
        nuevo = user_service.create_user(
            db, email=email, slug=slug, nombre_negocio=nombre_negocio, password=password
        )
    except ServiceError as e:
        return back_to("/super/users/new", error=e.message)
    return back_to("/super", ok=f"Usuario «{nuevo.nombre_negocio}» creado (/menu/{nuevo.slug})")


@router.get("/super/users/{user_id}/edit", response_class=HTMLResponse)
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
    return templates.TemplateResponse(
        request,
        "super/user_form.html",
        {"admin": admin, "modo": "editar", "target": target, "error": error},
    )


@router.post("/super/users/{user_id}/edit")
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
    try:
        user_service.update_user(
            db,
            target,
            email=email,
            slug=slug,
            nombre_negocio=nombre_negocio,
            is_active=bool(is_active),
            password=password,
            current_admin_id=admin.id,
        )
    except ServiceError as e:
        return back_to(f"/super/users/{user_id}/edit", error=e.message)
    return back_to("/super", ok="Usuario actualizado")


@router.post("/super/users/{user_id}/delete")
async def super_user_delete(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_super_admin),
):
    target = db.get(User, user_id)
    if not target:
        return back_to("/super", error="Usuario no encontrado")
    try:
        user_service.delete_user(db, target, current_admin_id=admin.id)
    except ServiceError as e:
        return back_to("/super", error=e.message)
    return back_to("/super", ok="Usuario eliminado")


@router.post("/super/users/{user_id}/impersonate")
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
