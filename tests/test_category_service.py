import pytest

from app.services import ServiceError
from app.services import category as cat_service


def _cats(db, user):
    db.refresh(user)
    return sorted(user.categorias, key=lambda c: c.orden)


def test_create_assigns_contiguous_orden(db_session, user):
    cat_service.create_category(db_session, user, "Uno")
    cat_service.create_category(db_session, user, "Dos")
    cat_service.create_category(db_session, user, "Tres")
    assert [c.orden for c in _cats(db_session, user)] == [0, 1, 2]
    assert [c.nombre for c in _cats(db_session, user)] == ["Uno", "Dos", "Tres"]


def test_create_rejects_empty(db_session, user):
    with pytest.raises(ServiceError):
        cat_service.create_category(db_session, user, "   ")


def test_create_rejects_too_long(db_session, user):
    with pytest.raises(ServiceError):
        cat_service.create_category(db_session, user, "x" * 41)


def test_move_down_swaps_and_keeps_orden_contiguous(db_session, user):
    for n in ("A", "B", "C"):
        cat_service.create_category(db_session, user, n)
    cats = _cats(db_session, user)
    cat_service.move_category(db_session, user, cats[0], "abajo")
    result = _cats(db_session, user)
    assert [c.nombre for c in result] == ["B", "A", "C"]
    assert [c.orden for c in result] == [0, 1, 2]


def test_move_up_at_top_is_noop(db_session, user):
    for n in ("A", "B"):
        cat_service.create_category(db_session, user, n)
    cats = _cats(db_session, user)
    cat_service.move_category(db_session, user, cats[0], "arriba")
    assert [c.nombre for c in _cats(db_session, user)] == ["A", "B"]


def test_move_invalid_direction_raises(db_session, user):
    cat_service.create_category(db_session, user, "A")
    cat = _cats(db_session, user)[0]
    with pytest.raises(ServiceError):
        cat_service.move_category(db_session, user, cat, "izquierda")


def test_delete_renumbers_remaining(db_session, user):
    for n in ("A", "B", "C"):
        cat_service.create_category(db_session, user, n)
    cats = _cats(db_session, user)
    cat_service.delete_category(db_session, user, cats[0])
    result = _cats(db_session, user)
    assert [c.nombre for c in result] == ["B", "C"]
    assert [c.orden for c in result] == [0, 1]


def test_set_price_mode_default_and_update(db_session, user):
    cat_service.create_category(db_session, user, "A")
    cat = _cats(db_session, user)[0]
    assert cat.precio_modo == "usd_fijo"
    cat_service.set_price_mode(db_session, cat, "usd_a_bss")
    assert _cats(db_session, user)[0].precio_modo == "usd_a_bss"


def test_set_price_mode_rejects_invalid(db_session, user):
    cat_service.create_category(db_session, user, "A")
    cat = _cats(db_session, user)[0]
    with pytest.raises(ServiceError):
        cat_service.set_price_mode(db_session, cat, "yenes")


def test_ownership_check(db_session, user, super_admin):
    cat_service.create_category(db_session, user, "Mine")
    cat = _cats(db_session, user)[0]
    # super_admin no es dueño de la categoría de user
    assert cat_service.get_owned_category(db_session, cat.id, super_admin) is None
    assert cat_service.get_owned_category(db_session, cat.id, user) is not None
