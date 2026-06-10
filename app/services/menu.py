"""Lógica de armado del menú público (paginación en pantallas + backgrounds)."""

import math
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import User


def get_active_user_by_slug(db: Session, slug: str) -> User | None:
    return db.query(User).filter(User.slug == slug, User.is_active.is_(True)).first()


def split_items_into_screens(items: list[dict], per_screen: int = 15) -> list[list[dict]]:
    """Reparte los items en N pantallas de tamaño ~equilibrado (>~15 items se parte)."""
    n = len(items)
    num_screens = max(1, math.ceil(n / per_screen)) if n > 0 else 1
    base, remainder = divmod(n, num_screens)
    out: list[list[dict]] = []
    start = 0
    for i in range(num_screens):
        size = base + (1 if i < remainder else 0)
        out.append(items[start : start + size])
        start += size
    return out


def resolve_background(path: str | None) -> str | None:
    """Devuelve la URL pública del background si el archivo existe, si no None."""
    if path and Path(path.lstrip("/")).exists():
        return f"/{path.lstrip('/')}"
    return None


def build_menu_payload(user: User) -> dict:
    cats = sorted(user.categorias, key=lambda c: c.orden)
    backgrounds = [resolve_background(c.background_path) for c in cats]
    pantallas: list[dict] = []
    for capa_idx, cat in enumerate(cats):
        items = [{"id": it.id, "nombre": it.nombre, "precio": it.precio} for it in cat.items]
        for chunk in split_items_into_screens(items):
            pantallas.append({"capa_idx": capa_idx, "categoria_nombre": cat.nombre, "items": chunk})
    return {
        "tiempo_rotacion": user.tiempo_rotacion_segundos,
        "backgrounds": backgrounds,
        "pantallas": pantallas,
    }
