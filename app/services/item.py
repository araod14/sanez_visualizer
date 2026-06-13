"""CRUD de productos (items), filtrado por dueño vía su categoría."""

from sqlalchemy.orm import Session

from app.models import ProductItem, User
from app.services import ServiceError


def get_owned_item(db: Session, item_id: int, user: User) -> ProductItem | None:
    item = db.get(ProductItem, item_id)
    if not item or item.categoria.user_id != user.id:
        return None
    return item


def _clean_precio(valor: str) -> str | None:
    """Normaliza un precio de tamaño opcional: trim + recorte, o None si vacío."""
    valor = (valor or "").strip()
    return valor[:30] if valor else None


def add_item(
    db: Session,
    category_id: int,
    nombre: str,
    precio: str,
    descripcion: str = "",
    precio_peq: str = "",
    precio_med: str = "",
    precio_gran: str = "",
) -> None:
    nombre = nombre.strip()
    if not nombre:
        raise ServiceError("El nombre del producto no puede estar vacío")
    precio = precio.strip()
    if not precio:
        raise ServiceError("El precio no puede estar vacío")
    descripcion = (descripcion or "").strip()
    total = db.query(ProductItem).filter(ProductItem.category_id == category_id).count()
    db.add(
        ProductItem(
            category_id=category_id,
            nombre=nombre[:80],
            precio=precio[:30],
            descripcion=descripcion[:200] or None,
            precio_peq=_clean_precio(precio_peq),
            precio_med=_clean_precio(precio_med),
            precio_gran=_clean_precio(precio_gran),
            orden=total,
        )
    )
    db.commit()


def edit_item(
    db: Session,
    item: ProductItem,
    nombre: str,
    precio: str,
    descripcion: str = "",
    precio_peq: str = "",
    precio_med: str = "",
    precio_gran: str = "",
) -> None:
    nombre = nombre.strip()
    precio = precio.strip()
    if not nombre:
        raise ServiceError("El nombre no puede estar vacío")
    if not precio:
        raise ServiceError("El precio no puede estar vacío")
    item.nombre = nombre[:80]
    item.precio = precio[:30]
    item.descripcion = (descripcion or "").strip()[:200] or None
    item.precio_peq = _clean_precio(precio_peq)
    item.precio_med = _clean_precio(precio_med)
    item.precio_gran = _clean_precio(precio_gran)
    db.commit()


def delete_item(db: Session, item: ProductItem) -> None:
    db.delete(item)
    db.commit()
