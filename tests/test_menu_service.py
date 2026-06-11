from app.services.menu import (
    build_menu_payload,
    compute_precio_bss,
    format_bss,
    parse_price,
    split_items_into_screens,
)


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
    assert pant["precio_modo"] == "usd_fijo"
    assert pant["items"] == [
        {"id": pant["items"][0]["id"], "nombre": "Polar", "precio": "2", "precio_bss": None}
    ]


# --- helpers de precio -------------------------------------------------------


def test_parse_price_punto():
    assert parse_price("45.50") == 45.5


def test_parse_price_coma():
    assert parse_price("45,50") == 45.5


def test_parse_price_con_simbolo():
    assert parse_price("$ 12") == 12.0


def test_parse_price_no_numerico():
    assert parse_price("Consultar") is None


def test_format_bss_miles_y_decimales():
    assert format_bss(1625.0) == "Bs 1.625,00"
    assert format_bss(45.5) == "Bs 45,50"


def test_compute_precio_bss_por_modo():
    # usd_fijo no usa conversión
    assert compute_precio_bss("10", "usd_fijo", 36.0) is None
    # bss_fijo formatea el crudo numérico
    assert compute_precio_bss("10", "bss_fijo", None) == "Bs 10,00"
    # usd_a_bss convierte con la tasa
    assert compute_precio_bss("10", "usd_a_bss", 36.0) == "Bs 360,00"
    # ambos también convierte
    assert compute_precio_bss("10", "ambos", 36.0) == "Bs 360,00"
    # sin tasa, la conversión no aplica
    assert compute_precio_bss("10", "usd_a_bss", None) is None
    # precio no numérico no se puede convertir
    assert compute_precio_bss("Consultar", "ambos", 36.0) is None


def _user_con_categoria(db_session, modo):
    from app.models import Category, ProductItem, User

    u = User(
        email=f"{modo}@x.com", slug=modo.replace("_", "-"), nombre_negocio="N", password_hash="h"
    )
    db_session.add(u)
    db_session.flush()
    cat = Category(user_id=u.id, nombre="Cat", orden=0, precio_modo=modo)
    db_session.add(cat)
    db_session.flush()
    db_session.add(ProductItem(category_id=cat.id, nombre="P", precio="10", orden=0))
    db_session.commit()
    db_session.refresh(u)
    return u


def test_build_menu_payload_modo_usd_a_bss(db_session):
    u = _user_con_categoria(db_session, "usd_a_bss")
    pant = build_menu_payload(u, usd_rate=36.0)["pantallas"][0]
    assert pant["precio_modo"] == "usd_a_bss"
    assert pant["items"][0]["precio"] == "10"
    assert pant["items"][0]["precio_bss"] == "Bs 360,00"


def test_build_menu_payload_modo_ambos(db_session):
    u = _user_con_categoria(db_session, "ambos")
    item = build_menu_payload(u, usd_rate=36.0)["pantallas"][0]["items"][0]
    assert item["precio"] == "10"
    assert item["precio_bss"] == "Bs 360,00"


def test_build_menu_payload_sin_tasa_cae_a_none(db_session):
    u = _user_con_categoria(db_session, "usd_a_bss")
    item = build_menu_payload(u, usd_rate=None)["pantallas"][0]["items"][0]
    assert item["precio_bss"] is None
