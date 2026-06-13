"""Dependencias de autenticación y la excepción de redirección a login."""

from fastapi import Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User


class RedirectToLogin(Exception):
    """Se levanta cuando falta autenticación; el handler redirige a /login."""


async def redirect_to_login_handler(request: Request, exc: RedirectToLogin) -> RedirectResponse:
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
        raise RedirectToLogin()
    return user


def require_super_admin(request: Request, db: Session = Depends(get_db)) -> User:
    user = current_user(request, db)
    if not user or not user.is_super_admin:
        raise RedirectToLogin()
    return user
