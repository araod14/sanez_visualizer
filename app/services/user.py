"""Validación de slug, estadísticas y CRUD de usuarios (super-admin)."""

import re

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Category, ProductItem, User
from app.security.passwords import hash_password
from app.services import ServiceError
from app.services.upload import delete_user_dir

SLUG_REGEX = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?$")
RESERVED_SLUGS = {"admin", "super", "api", "login", "logout", "static", "menu", ""}


def validar_slug(slug: str) -> str | None:
    slug = (slug or "").strip().lower()
    if slug in RESERVED_SLUGS:
        return None
    if not SLUG_REGEX.match(slug):
        return None
    return slug


def user_stats(db: Session) -> list[dict]:
    """Lista usuarios con sus conteos de categorías/items (sin N+1)."""
    usuarios = db.query(User).order_by(User.is_super_admin.desc(), User.created_at.desc()).all()
    cat_counts = dict(
        db.query(Category.user_id, func.count(Category.id)).group_by(Category.user_id).all()
    )
    item_counts = dict(
        db.query(Category.user_id, func.count(ProductItem.id))
        .join(ProductItem, ProductItem.category_id == Category.id)
        .group_by(Category.user_id)
        .all()
    )
    return [
        {"u": u, "n_cats": cat_counts.get(u.id, 0), "n_items": item_counts.get(u.id, 0)}
        for u in usuarios
    ]


def create_user(db: Session, *, email: str, slug: str, nombre_negocio: str, password: str) -> User:
    email = email.strip().lower()
    nombre_negocio = nombre_negocio.strip()
    slug_v = validar_slug(slug)
    if not email or "@" not in email:
        raise ServiceError("Email inválido")
    if not slug_v:
        raise ServiceError("Slug inválido (solo letras/números/guion, no reservado)")
    if not nombre_negocio:
        raise ServiceError("Nombre del negocio requerido")
    if len(password) < 6:
        raise ServiceError("La contraseña debe tener al menos 6 caracteres")
    if db.query(User).filter(User.email == email).first():
        raise ServiceError("Email ya registrado")
    if db.query(User).filter(User.slug == slug_v).first():
        raise ServiceError("Slug ya en uso")

    nuevo = User(
        email=email,
        slug=slug_v,
        nombre_negocio=nombre_negocio[:80],
        password_hash=hash_password(password),
        is_active=True,
        is_super_admin=False,
    )
    db.add(nuevo)
    db.commit()
    return nuevo


def update_user(
    db: Session,
    target: User,
    *,
    email: str,
    slug: str,
    nombre_negocio: str,
    is_active: bool,
    password: str,
    current_admin_id: int,
) -> None:
    email = email.strip().lower()
    nombre_negocio = nombre_negocio.strip()
    slug_v = validar_slug(slug)
    if not email or "@" not in email:
        raise ServiceError("Email inválido")
    if not slug_v:
        raise ServiceError("Slug inválido")
    if not nombre_negocio:
        raise ServiceError("Nombre del negocio requerido")
    if password and len(password) < 6:
        raise ServiceError("La contraseña debe tener al menos 6 caracteres")
    if db.query(User).filter(User.email == email, User.id != target.id).first():
        raise ServiceError("Email ya registrado")
    if db.query(User).filter(User.slug == slug_v, User.id != target.id).first():
        raise ServiceError("Slug ya en uso")

    target.email = email
    target.slug = slug_v
    target.nombre_negocio = nombre_negocio[:80]
    # No permitir desactivar al propio super-admin actual.
    if target.id != current_admin_id:
        target.is_active = is_active
    if password:
        target.password_hash = hash_password(password)
    db.commit()


def delete_user(db: Session, target: User, *, current_admin_id: int) -> None:
    if target.id == current_admin_id:
        raise ServiceError("No puedes eliminar tu propia cuenta")
    if target.is_super_admin:
        raise ServiceError("No se puede eliminar otro super-admin desde aquí")
    delete_user_dir(target.id)
    db.delete(target)
    db.commit()
