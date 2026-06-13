"""Engine, sessionmaker y dependencia `get_db`.

El esquema lo posee Alembic en producción; `create_all()` queda disponible
para los tests (y para el shim de compatibilidad legacy).
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models import Base

_settings = get_settings()


def _connect_args(url: str) -> dict:
    return {"check_same_thread": False} if url.startswith("sqlite") else {}


engine = create_engine(_settings.database_url, connect_args=_connect_args(_settings.database_url))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_all() -> None:
    """Crea todas las tablas. Lo usan los tests; en prod lo hace Alembic."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
