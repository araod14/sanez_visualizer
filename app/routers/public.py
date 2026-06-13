"""Rutas públicas: login/logout, menú público, API de datos y tasas."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import current_user
from app.models import ExchangeRate, User
from app.security.passwords import verify_password
from app.services.menu import build_menu_payload, get_active_user_by_slug
from app.services.rates import list_rates
from app.templates import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def root(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if user:
        return RedirectResponse(url="/super" if user.is_super_admin else "/admin", status_code=302)
    return RedirectResponse(url="/login", status_code=302)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    return templates.TemplateResponse(request, "login.html", {"error": error})


@router.post("/login")
async def login_submit(
    request: Request,
    db: Session = Depends(get_db),
    usuario: str = Form(...),
    contrasena: str = Form(...),
):
    limiter = request.app.state.login_limiter
    ip = request.client.host if request.client else "unknown"
    if limiter.is_blocked(ip):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Demasiados intentos fallidos. Espera unos minutos e inténtalo de nuevo."},
            status_code=429,
        )

    user = db.query(User).filter(User.email == usuario.strip().lower()).first()
    if not user or not user.is_active or not verify_password(contrasena, user.password_hash):
        limiter.record_failure(ip)
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Usuario o contraseña incorrectos."},
            status_code=401,
        )
    limiter.reset(ip)
    request.session.clear()
    request.session["user_id"] = user.id
    return RedirectResponse(url="/super" if user.is_super_admin else "/admin", status_code=302)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


@router.get("/api/exchange-rates")
async def api_exchange_rates(db: Session = Depends(get_db)):
    return list_rates(db)


@router.get("/menu/{slug}", response_class=HTMLResponse)
async def pantalla_publica(request: Request, slug: str, db: Session = Depends(get_db)):
    user = get_active_user_by_slug(db, slug)
    if not user:
        raise HTTPException(status_code=404, detail="Menú no encontrado")
    return templates.TemplateResponse(
        request, "public.html", {"slug": slug, "nombre_negocio": user.nombre_negocio}
    )


@router.get("/api/data/{slug}")
async def api_data(slug: str, db: Session = Depends(get_db)):
    user = get_active_user_by_slug(db, slug)
    if not user:
        raise HTTPException(status_code=404, detail="Menú no encontrado")
    usd = db.get(ExchangeRate, "USD")
    usd_rate = usd.rate if usd else None
    return JSONResponse(build_menu_payload(user, usd_rate))
