from app.services.menu import build_menu_payload, split_items_into_screens


def test_split_empty():
    assert split_items_into_screens([]) == [[]]


def test_split_single():
    assert split_items_into_screens([{"x": 1}]) == [[{"x": 1}]]


def test_split_exactly_15():
    items = list(range(15))
    screens = split_items_into_screens(items)
    assert [len(s) for s in screens] == [15]


def test_split_16_balances_two_screens():
    screens = split_items_into_screens(list(range(16)))
    assert [len(s) for s in screens] == [8, 8]


def test_split_31_balances_three_screens():
    screens = split_items_into_screens(list(range(31)))
    assert [len(s) for s in screens] == [11, 10, 10]


def test_split_preserves_order_and_completeness():
    items = list(range(31))
    screens = split_items_into_screens(items)
    flat = [x for s in screens for x in s]
    assert flat == items


def test_build_menu_payload_shape(db_session):
    from app.models import Category, ProductItem, User

    u = User(
        email="m@x.com",
        slug="m1",
        nombre_negocio="N",
        password_hash="h",
        tiempo_rotacion_segundos=7,
    )
    db_session.add(u)
    db_session.flush()
    cat = Category(user_id=u.id, nombre="Cervezas", orden=0)
    db_session.add(cat)
    db_session.flush()
    db_session.add(ProductItem(category_id=cat.id, nombre="Polar", precio="2", orden=0))
    db_session.commit()
    db_session.refresh(u)

    payload = build_menu_payload(u)
    assert payload["tiempo_rotacion"] == 7
    assert payload["backgrounds"] == [None]
    assert len(payload["pantallas"]) == 1
    pant = payload["pantallas"][0]
    assert pant["capa_idx"] == 0
    assert pant["categoria_nombre"] == "Cervezas"
    assert pant["items"] == [{"id": pant["items"][0]["id"], "nombre": "Polar", "precio": "2"}]
