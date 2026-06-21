"""CRUD y reordenamiento de categorías (filtrado por dueño)."""

from sqlalchemy.orm import Session

from app.models import Category, User
from app.services import ServiceError
from app.services.menu import PRICE_MODES
from app.services.upload import (
    delete_category_preview,
    delete_file_if_exists,
    read_category_preview,
    save_category_image,
)


def get_owned_category(db: Session, cat_id: int, user: User) -> Category | None:
    cat = db.get(Category, cat_id)
    return cat if cat and cat.user_id == user.id else None


def _renumber_contiguous(db: Session, cats: list[Category]) -> None:
    """Reasigna ordenes 0..n-1 esquivando UniqueConstraint(user_id, orden)."""
    for i, c in enumerate(cats):
        c.orden = -(i + 1)
    db.flush()
    for i, c in enumerate(cats):
        c.orden = i


def create_category(db: Session, user: User, nombre: str) -> str:
    nombre = nombre.strip()
    if not nombre:
        raise ServiceError("El nombre no puede estar vacío")
    if len(nombre) > 40:
        raise ServiceError("Nombre demasiado largo (máx 40)")
    max_orden = db.query(Category).filter(Category.user_id == user.id).count()
    db.add(Category(user_id=user.id, nombre=nombre, orden=max_orden))
    db.commit()
    return nombre


def rename_category(db: Session, cat: Category, nombre: str) -> None:
    nombre = nombre.strip()
    if not nombre:
        raise ServiceError("El nombre no puede estar vacío")
    cat.nombre = nombre[:40]
    db.commit()


def set_price_mode(db: Session, cat: Category, modo: str) -> None:
    if modo not in PRICE_MODES:
        raise ServiceError("Modo de precio inválido")
    cat.precio_modo = modo
    db.commit()


def move_category(db: Session, user: User, cat: Category, direccion: str) -> None:
    if direccion not in {"arriba", "abajo"}:
        raise ServiceError("Dirección inválida")
    ordenadas = sorted(user.categorias, key=lambda c: c.orden)
    idx = next((i for i, c in enumerate(ordenadas) if c.id == cat.id), -1)
    objetivo = idx - 1 if direccion == "arriba" else idx + 1
    if idx < 0 or not (0 <= objetivo < len(ordenadas)):
        return
    ordenadas[idx], ordenadas[objetivo] = ordenadas[objetivo], ordenadas[idx]
    _renumber_contiguous(db, ordenadas)
    db.commit()


def set_category_background(
    db: Session, user: User, cat: Category, filename: str, content: bytes
) -> None:
    cat.background_path = save_category_image(
        user.id, cat.id, filename, content, cat.background_path
    )
    db.commit()


def confirm_generated_background(db: Session, user: User, cat: Category) -> None:
    """Promueve la previsualización generada por IA a fondo definitivo."""
    content = read_category_preview(user.id, cat.id)
    if content is None:
        raise ServiceError("No hay ninguna previsualización para guardar")
    cat.background_path = save_category_image(
        user.id, cat.id, "bg.png", content, cat.background_path
    )
    delete_category_preview(user.id, cat.id)
    db.commit()


def delete_category(db: Session, user: User, cat: Category) -> str:
    delete_file_if_exists(cat.background_path)
    delete_category_preview(user.id, cat.id)
    nombre = cat.nombre
    db.delete(cat)
    db.commit()
    restantes = sorted(
        db.query(Category).filter(Category.user_id == user.id).all(),
        key=lambda c: c.orden,
    )
    _renumber_contiguous(db, restantes)
    db.commit()
    return nombre
