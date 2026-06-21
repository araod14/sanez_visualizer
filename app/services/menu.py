"""Lógica de armado del menú público (paginación en pantallas + backgrounds)."""

import math
import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import User

# Modos de precio por categoría:
#   usd_fijo  -> precio fijo en dólares (se muestra "$ <precio>")
#   bss_fijo  -> precio fijo en bolívares (se muestra "Bs <precio>")
#   usd_a_bss -> el precio se carga en dólares y se convierte a Bs con la tasa USD
#   ambos     -> se muestran ambos: dólares y su conversión a Bs
PRICE_MODES = {"usd_fijo", "bss_fijo", "usd_a_bss", "ambos"}
DEFAULT_PRICE_MODE = "usd_fijo"

# Estilos visuales de la cartelera pública (se elige uno por usuario):
#   estilo_1 -> restaurante clásico   estilo_2 -> tarjetas oscuras
#   estilo_3 -> carta de pizzería     estilo_4 -> bar nocturno / neón
#   estilo_5 -> minimalista elegante
LIST_STYLES = {"estilo_1", "estilo_2", "estilo_3", "estilo_4", "estilo_5"}
DEFAULT_LIST_STYLE = "estilo_1"

# Etiquetas de tamaño para el estilo pizzería (col -> etiqueta mostrada).
_SIZE_LABELS = (("precio_peq", "Peq."), ("precio_med", "Med."), ("precio_gran", "Gran."))

_NUM_RE = re.compile(r"[+-]?\d+(?:[.,]\d+)?")


def parse_price(precio: str) -> float | None:
    """Extrae el valor numérico de un precio libre (acepta coma o punto decimal).

    Devuelve None si no contiene un número (ej. "Consultar").
    """
    if precio is None:
        return None
    m = _NUM_RE.search(precio.strip())
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", "."))
    except ValueError:
        return None


def format_bss(value: float) -> str:
    """Formatea un monto como 'Bs 1.625,00' (miles con punto, decimal con coma)."""
    entero = f"{value:,.2f}"  # 1,625.00  (formato en-US)
    # swap: coma<->punto para obtener formato es-VE
    entero = entero.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return f"Bs {entero}"


def get_active_user_by_slug(db: Session, slug: str) -> User | None:
    return db.query(User).filter(User.slug == slug, User.is_active.is_(True)).first()


def compute_precio_bss(precio: str, modo: str, usd_rate: float | None) -> str | None:
    """String BsS ya formateado para el item, o None si el modo no lo usa o no aplica."""
    if modo == "bss_fijo":
        n = parse_price(precio)
        return format_bss(n) if n is not None else None
    if modo in ("usd_a_bss", "ambos"):
        n = parse_price(precio)
        if n is None or usd_rate is None:
            return None
        return format_bss(n * usd_rate)
    return None


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
    """Devuelve la URL pública del background si el archivo existe, si no None.

    El `path` guardado es una ruta de filesystem (relativa en producción,
    p.ej. `static/uploads/...`; puede ser absoluta si `UPLOAD_DIR` lo es).
    Se chequea la existencia tal cual y se sirve la URL con un único `/` inicial.
    """
    if path and Path(path).exists():
        return f"/{path.lstrip('/')}"
    return None


def _item_tamanos(it, modo: str, usd_rate: float | None) -> list[dict]:
    """Lista de tamaños (Peq./Med./Gran.) con precio presente, formateando BsS."""
    tamanos = []
    for col, etiqueta in _SIZE_LABELS:
        precio = getattr(it, col, None)
        if precio:
            tamanos.append(
                {
                    "etiqueta": etiqueta,
                    "precio": precio,
                    "precio_bss": compute_precio_bss(precio, modo, usd_rate),
                }
            )
    return tamanos


def build_menu_payload(user: User, usd_rate: float | None = None) -> dict:
    cats = sorted(user.categorias, key=lambda c: c.orden)
    backgrounds = [resolve_background(c.background_path) for c in cats]
    pantallas: list[dict] = []
    for capa_idx, cat in enumerate(cats):
        modo = cat.precio_modo or DEFAULT_PRICE_MODE
        items = [
            {
                "id": it.id,
                "nombre": it.nombre,
                "precio": it.precio,
                "precio_bss": compute_precio_bss(it.precio, modo, usd_rate),
                "descripcion": it.descripcion or "",
                "tamanos": _item_tamanos(it, modo, usd_rate),
            }
            for it in cat.items
        ]
        for chunk in split_items_into_screens(items):
            pantallas.append(
                {
                    "capa_idx": capa_idx,
                    "categoria_nombre": cat.nombre,
                    "precio_modo": modo,
                    "items": chunk,
                }
            )
    return {
        "tiempo_rotacion": user.tiempo_rotacion_segundos,
        "estilo_lista": user.estilo_lista or DEFAULT_LIST_STYLE,
        "backgrounds": backgrounds,
        "pantallas": pantallas,
    }
