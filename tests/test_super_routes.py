from app.services.user import user_stats
from tests.helpers import login, post_with_csrf


def test_create_user_via_route(client, super_admin, db_session):
    login(client, "admin@x.com", "secret6")
    r = post_with_csrf(
        client,
        "/super/users",
        {
            "email": "biz@x.com",
            "slug": "pizza",
            "nombre_negocio": "Pizza",
            "password": "secret6",
        },
        token_path="/super/users/new",
    )
    assert r.status_code == 302
    assert "ok=" in r.headers["location"]
    from app.models import User

    assert db_session.query(User).filter(User.slug == "pizza").first() is not None


def test_create_user_invalid_slug_rejected(client, super_admin):
    login(client, "admin@x.com", "secret6")
    r = post_with_csrf(
        client,
        "/super/users",
        {
            "email": "biz@x.com",
            "slug": "admin",  # reservado
            "nombre_negocio": "Pizza",
            "password": "secret6",
        },
        token_path="/super/users/new",
    )
    assert "error=" in r.headers["location"]


def test_create_user_short_password_rejected(client, super_admin):
    login(client, "admin@x.com", "secret6")
    r = post_with_csrf(
        client,
        "/super/users",
        {"email": "biz@x.com", "slug": "pizza", "nombre_negocio": "Pizza", "password": "123"},
        token_path="/super/users/new",
    )
    assert "error=" in r.headers["location"]


def test_impersonate_and_stop(client, super_admin, user):
    login(client, "admin@x.com", "secret6")
    r = post_with_csrf(client, f"/super/users/{user.id}/impersonate", {}, token_path="/super")
    assert r.headers["location"] == "/admin"
    # ahora estamos como el usuario impersonado
    assert client.get("/admin", follow_redirects=False).status_code == 200
    r = post_with_csrf(client, "/admin/stop-impersonating", {}, token_path="/admin")
    assert r.headers["location"] == "/super"


def test_user_stats_counts(db_session, user):
    from app.services import category as cat_service
    from app.services import item as item_service

    cat_service.create_category(db_session, user, "C1")
    cat = sorted(user.categorias, key=lambda c: c.orden)[0]
    item_service.add_item(db_session, cat.id, "i1", "1")
    item_service.add_item(db_session, cat.id, "i2", "2")

    stats = {row["u"].id: row for row in user_stats(db_session)}
    assert stats[user.id]["n_cats"] == 1
    assert stats[user.id]["n_items"] == 2
