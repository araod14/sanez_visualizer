"""Protección CSRF basada en un token de sesión.

`verify_csrf` se registra como dependencia global de la app y valida el token
en toda petición mutante. `get_csrf_token` lo inyecta en las plantillas.
"""

import secrets

from fastapi import HTTPException, Request

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
