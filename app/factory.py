"""Application factory: ensambla la app FastAPI con todas sus piezas."""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.bootstrap import init_db
from app.config import get_settings
from app.db import create_all
from app.dependencies import RedirectToLogin, redirect_to_login_handler
from app.routers import admin, public, superadmin
from app.scheduler import build_scheduler
from app.security.csrf import verify_csrf
from app.security.rate_limit import LoginRateLimiter


def create_app() -> FastAPI:
    settings = get_settings()
    if not settings.secret_key:  # defensa extra; Settings ya falla-duro si falta
        raise RuntimeError("SECRET_KEY no configurada.")

    scheduler = build_scheduler(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        create_all()
        init_db(settings)
        if settings.scheduler_enabled:
            scheduler.start()
        yield
        if scheduler.running:
            scheduler.shutdown(wait=False)

    app = FastAPI(title="Visual Panel", lifespan=lifespan, dependencies=[Depends(verify_csrf)])
    app.state.login_limiter = LoginRateLimiter(
        settings.login_max_attempts, settings.login_window_seconds
    )
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        https_only=settings.session_https_only,
        same_site=settings.session_same_site,
    )
    app.mount("/static", StaticFiles(directory="static"), name="static")
    app.add_exception_handler(RedirectToLogin, redirect_to_login_handler)
    for r in (public.router, admin.router, superadmin.router):
        app.include_router(r)
    return app
