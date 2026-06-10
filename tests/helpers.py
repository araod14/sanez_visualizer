"""Utilidades para los tests de rutas (manejo del token CSRF y login)."""

import re

_CSRF_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


def csrf_token(client, path: str = "/login") -> str:
    """Renderiza una página y extrae su token CSRF (sembrado en la sesión)."""
    html = client.get(path).text
    m = _CSRF_RE.search(html)
    assert m, f"No se encontró csrf_token en {path}"
    return m.group(1)


def post_with_csrf(client, url: str, data: dict, *, token_path: str = "/login", **kwargs):
    data = {**data, "csrf_token": csrf_token(client, token_path)}
    return client.post(url, data=data, follow_redirects=False, **kwargs)


def login(client, email: str, password: str):
    return post_with_csrf(client, "/login", {"usuario": email, "contrasena": password})
