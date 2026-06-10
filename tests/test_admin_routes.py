from tests.helpers import login, post_with_csrf


def test_create_category_appears_in_dashboard(client, user):
    login(client, "user@x.com", "secret6")
    r = post_with_csrf(client, "/admin/categories", {"nombre": "Tragos"}, token_path="/admin")
    assert r.status_code == 302
    assert client.get("/admin").text.count("Tragos") >= 1


def test_settings_bounds_rejected(client, user):
    login(client, "user@x.com", "secret6")
    r = post_with_csrf(client, "/admin/settings", {"tiempo_rotacion": "1"}, token_path="/admin")
    assert r.status_code == 302
    assert "error=" in r.headers["location"]


def test_settings_valid_updates(client, user, db_session):
    login(client, "user@x.com", "secret6")
    r = post_with_csrf(client, "/admin/settings", {"tiempo_rotacion": "20"}, token_path="/admin")
    assert "ok=" in r.headers["location"]
    db_session.refresh(user)
    assert user.tiempo_rotacion_segundos == 20


def test_add_item_to_category(client, user, db_session):
    from app.services import category as cat_service

    cat_service.create_category(db_session, user, "Cervezas")
    cat = sorted(user.categorias, key=lambda c: c.orden)[0]
    login(client, "user@x.com", "secret6")
    r = post_with_csrf(
        client,
        "/admin/items/add",
        {"category_id": str(cat.id), "nombre": "Polar", "precio": "2"},
        token_path="/admin",
    )
    assert "ok=" in r.headers["location"]
    data = client.get(f"/api/data/{user.slug}").json()
    nombres = [it["nombre"] for p in data["pantallas"] for it in p["items"]]
    assert "Polar" in nombres


def test_csrf_rejected_on_admin_post(client, user):
    login(client, "user@x.com", "secret6")
    r = client.post("/admin/categories", data={"nombre": "X"}, follow_redirects=False)
    assert r.status_code == 403
