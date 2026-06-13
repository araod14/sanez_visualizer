"""Seed idempotente del super-admin. El esquema lo crea `app.db.create_all`
(o Alembic); aquí solo se inserta la fila inicial si no existe."""

from app.config import Settings
from app.db import SessionLocal
from app.models import User
from app.security.passwords import hash_password


def init_db(settings: Settings) -> None:
    db = SessionLocal()
    try:
        if db.query(User).filter(User.is_super_admin.is_(True)).first():
            return
        email = settings.effective_super_admin_email
        password = settings.effective_super_admin_password
        db.add(
            User(
                email=email,
                slug="super",
                nombre_negocio="Super Admin",
                password_hash=hash_password(password),
                is_active=True,
                is_super_admin=True,
            )
        )
        db.commit()
        print(f"Super-admin creado: email={email}")
    finally:
        db.close()
