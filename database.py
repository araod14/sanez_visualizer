"""Shim de compatibilidad — el código real vive en `app.*`.

Se mantiene mientras `main.py`, `scrapers/` y `scripts/` siguen importando
`from database import ...`. Se elimina en el paso final del refactor, una vez
que esos módulos apunten directamente a `app.*`.
"""

from app.config import get_settings
from app.db import SessionLocal, create_all, engine, get_db
from app.models import Base, Category, ExchangeRate, ProductItem, User
from app.security.passwords import hash_password, verify_password

__all__ = [
    "Base",
    "User",
    "Category",
    "ProductItem",
    "ExchangeRate",
    "engine",
    "SessionLocal",
    "get_db",
    "create_all",
    "hash_password",
    "verify_password",
    "init_db",
]


def init_db() -> None:
    """Crea tablas y bootstrapea el super-admin si no existe (idempotente)."""
    create_all()
    settings = get_settings()
    db = SessionLocal()
    try:
        existing_super = db.query(User).filter(User.is_super_admin.is_(True)).first()
        if existing_super:
            return
        email = settings.effective_super_admin_email
        password = settings.effective_super_admin_password
        super_admin = User(
            email=email,
            slug="super",
            nombre_negocio="Super Admin",
            password_hash=hash_password(password),
            is_active=True,
            is_super_admin=True,
        )
        db.add(super_admin)
        db.commit()
        print(f"Super-admin creado: email={email}")
    finally:
        db.close()
