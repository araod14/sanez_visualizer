def test_menu_404_for_unknown_slug(client):
    assert client.get("/menu/nope").status_code == 404


def test_menu_200_for_known_slug(client, user):
    r = client.get(f"/menu/{user.slug}")
    assert r.status_code == 200


def test_inactive_user_menu_404(client, user, db_session):
    user.is_active = False
    db_session.commit()
    assert client.get(f"/menu/{user.slug}").status_code == 404


def test_api_data_payload_shape(client, user, db_session):
    from app.services import category as cat_service
    from app.services import item as item_service

    cat_service.create_category(db_session, user, "Cervezas")
    cat = sorted(user.categorias, key=lambda c: c.orden)[0]
    item_service.add_item(db_session, cat.id, "Polar", "2")

    data = client.get(f"/api/data/{user.slug}").json()
    assert set(data.keys()) == {"tiempo_rotacion", "backgrounds", "pantallas"}
    assert data["backgrounds"] == [None]
    assert data["pantallas"][0]["categoria_nombre"] == "Cervezas"
    assert data["pantallas"][0]["items"][0]["nombre"] == "Polar"


def test_exchange_rates_endpoint(client):
    assert client.get("/api/exchange-rates").json() == {}
