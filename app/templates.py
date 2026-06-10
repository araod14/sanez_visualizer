"""Instancia compartida de Jinja2 con el `csrf_token` inyectado en el contexto."""

from fastapi.templating import Jinja2Templates

from app.security.csrf import get_csrf_token

templates = Jinja2Templates(
    directory="templates",
    context_processors=[lambda request: {"csrf_token": get_csrf_token(request)}],
)
