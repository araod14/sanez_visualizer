import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def settings(monkeypatch, tmp_path):
    """Entorno de test: clave fija, scheduler apagado, uploads a tmp."""
    monkeypatch.setenv("DEV_MODE", "1")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("SCHEDULER_ENABLED", "0")
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    from app.config import get_settings

    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest.fixture
def engine(settings):
    """Engine in-memory compartido (StaticPool) con el esquema creado."""
    from app.models import Base

    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def Session(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture
def db_session(Session):
    s = Session()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def client(settings, engine, Session):
    """TestClient cuyas rutas usan el mismo engine in-memory que db_session."""
    from app.db import get_db
    from app.factory import create_app

    app = create_app()

    def _override():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c


def _make_user(db, Session, **kwargs):
    from app.models import User
    from app.security.passwords import hash_password

    defaults = {
        "email": "user@x.com",
        "slug": "user1",
        "nombre_negocio": "Negocio",
        "password_hash": hash_password("secret6"),
        "is_active": True,
        "is_super_admin": False,
    }
    defaults.update(kwargs)
    u = User(**defaults)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def user(db_session, Session):
    return _make_user(db_session, Session)


@pytest.fixture
def super_admin(db_session, Session):
    return _make_user(
        db_session,
        Session,
        email="admin@x.com",
        slug="super",
        nombre_negocio="Super Admin",
        is_super_admin=True,
    )
