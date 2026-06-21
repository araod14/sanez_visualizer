"""Tests del flujo de fondos generados por IA (generate / confirm / discard)."""

from pathlib import Path

import pytest

from app.services import ServiceError, image_gen
from app.services import category as cat_service
from app.services.upload import category_preview_path
from tests.helpers import login, post_with_csrf

_FAKE_PNG = b"\x89PNG\r\n\x1a\nfake-image-bytes"


def _make_category(db_session, user, nombre="Cervezas"):
    cat_service.create_category(db_session, user, nombre)
    return sorted(user.categorias, key=lambda c: c.orden)[0]


def _mock_generation(monkeypatch, content=_FAKE_PNG):
    monkeypatch.setattr("app.services.image_gen.generate_background_image", lambda prompt: content)


# --- build_prompt (unit) ---------------------------------------------------


def test_build_prompt_vacio_rechazado():
    with pytest.raises(ServiceError):
        image_gen.build_prompt("   ")


def test_build_prompt_incluye_la_frase():
    prompt = image_gen.build_prompt("playa al atardecer")
    assert "playa al atardecer" in prompt


# --- sin API key -----------------------------------------------------------


def test_generate_sin_api_key_devuelve_error(client, user, db_session):
    cat = _make_category(db_session, user)
    login(client, "user@x.com", "secret6")
    r = post_with_csrf(
        client,
        f"/admin/categories/{cat.id}/background/generate",
        {"prompt": "madera rústica"},
        token_path="/admin",
    )
    assert r.status_code == 302
    assert "error=" in r.headers["location"]


# --- generate / confirm / discard (con generación mockeada) ----------------


def test_generate_crea_preview(client, user, db_session, monkeypatch):
    cat = _make_category(db_session, user)
    _mock_generation(monkeypatch)
    login(client, "user@x.com", "secret6")
    r = post_with_csrf(
        client,
        f"/admin/categories/{cat.id}/background/generate",
        {"prompt": "playa al atardecer"},
        token_path="/admin",
    )
    assert r.status_code == 302
    assert f"preview={cat.id}" in r.headers["location"]
    assert Path(category_preview_path(user.id, cat.id)).is_file()
    # El bloque de previsualización aparece al cargar /admin con ?preview=<id>.
    dashboard = client.get(f"/admin?preview={cat.id}&prompt=playa").text
    assert "Previsualización generada por IA" in dashboard


def test_confirm_promueve_a_fondo_y_borra_preview(client, user, db_session, monkeypatch):
    cat = _make_category(db_session, user)
    _mock_generation(monkeypatch)
    login(client, "user@x.com", "secret6")
    post_with_csrf(
        client,
        f"/admin/categories/{cat.id}/background/generate",
        {"prompt": "neón urbano"},
        token_path="/admin",
    )
    r = post_with_csrf(
        client,
        f"/admin/categories/{cat.id}/background/confirm",
        {},
        token_path="/admin",
    )
    assert "ok=" in r.headers["location"]
    db_session.refresh(cat)
    assert cat.background_path and Path(cat.background_path).is_file()
    assert not Path(category_preview_path(user.id, cat.id)).exists()


def test_confirm_sin_preview_devuelve_error(client, user, db_session):
    cat = _make_category(db_session, user)
    login(client, "user@x.com", "secret6")
    r = post_with_csrf(
        client,
        f"/admin/categories/{cat.id}/background/confirm",
        {},
        token_path="/admin",
    )
    assert "error=" in r.headers["location"]


def test_discard_borra_preview(client, user, db_session, monkeypatch):
    cat = _make_category(db_session, user)
    _mock_generation(monkeypatch)
    login(client, "user@x.com", "secret6")
    post_with_csrf(
        client,
        f"/admin/categories/{cat.id}/background/generate",
        {"prompt": "minimalista"},
        token_path="/admin",
    )
    assert Path(category_preview_path(user.id, cat.id)).is_file()
    r = post_with_csrf(
        client,
        f"/admin/categories/{cat.id}/background/discard",
        {},
        token_path="/admin",
    )
    assert "ok=" in r.headers["location"]
    assert not Path(category_preview_path(user.id, cat.id)).exists()


def test_generate_categoria_ajena_rechazada(client, user, db_session, Session, monkeypatch):
    from tests.conftest import _make_user

    otro = _make_user(db_session, Session, email="otro@x.com", slug="otro")
    cat_otro = _make_category(db_session, otro, nombre="DeOtro")
    _mock_generation(monkeypatch)
    login(client, "user@x.com", "secret6")
    r = post_with_csrf(
        client,
        f"/admin/categories/{cat_otro.id}/background/generate",
        {"prompt": "x"},
        token_path="/admin",
    )
    assert "error=" in r.headers["location"]
    assert not Path(category_preview_path(otro.id, cat_otro.id)).exists()
