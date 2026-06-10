import os
from datetime import datetime, timezone

import bcrypt
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker

DATABASE_URL = "sqlite:///./sanez.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _coerce_password(plain: str) -> bytes:
    # bcrypt impone un máximo de 72 bytes — truncamos en el borde para evitar ValueError.
    return (plain or "").encode("utf-8")[:72]


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_coerce_password(plain), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(_coerce_password(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False, index=True)
    slug = Column(String, unique=True, nullable=False, index=True)
    nombre_negocio = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_super_admin = Column(Boolean, default=False, nullable=False)
    tiempo_rotacion_segundos = Column(Integer, default=10, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    categorias = relationship(
        "Category",
        back_populates="usuario",
        order_by="Category.orden",
        cascade="all, delete-orphan",
    )


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("user_id", "orden", name="uq_category_user_orden"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    nombre = Column(String, nullable=False)
    orden = Column(Integer, nullable=False, default=0)
    background_path = Column(String, nullable=True)

    usuario = relationship("User", back_populates="categorias")
    items = relationship(
        "ProductItem",
        back_populates="categoria",
        order_by="ProductItem.orden",
        cascade="all, delete-orphan",
    )


class ProductItem(Base):
    __tablename__ = "product_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False, index=True)
    nombre = Column(String, nullable=False)
    precio = Column(String, nullable=False)
    orden = Column(Integer, nullable=False, default=0)

    categoria = relationship("Category", back_populates="items")


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"
    currency = Column(String, primary_key=True)  # "USD" | "EUR"
    rate = Column(Float, nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing_super = db.query(User).filter(User.is_super_admin.is_(True)).first()
        if existing_super:
            return

        email = os.environ.get("SUPER_ADMIN_EMAIL") or os.environ.get("ADMIN_USER", "admin")
        password = os.environ.get("SUPER_ADMIN_PASSWORD") or os.environ.get("ADMIN_PASSWORD", "admin")
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


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
