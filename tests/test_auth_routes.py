from tests.helpers import csrf_token, login


def test_login_page_ok(client):
    assert client.get("/login").status_code == 200


def test_login_success_redirects_super(client, super_admin):
    r = login(client, "admin@x.com", "secret6")
    assert r.status_code == 302
    assert r.headers["location"] == "/super"


def test_login_success_redirects_admin(client, user):
    r = login(client, "user@x.com", "secret6")
    assert r.status_code == 302
    assert r.headers["location"] == "/admin"


def test_login_bad_password_401(client, user):
    r = login(client, "user@x.com", "wrong-pass")
    assert r.status_code == 401


def test_login_without_csrf_is_403(client, user):
    r = client.post(
        "/login", data={"usuario": "user@x.com", "contrasena": "secret6"}, follow_redirects=False
    )
    assert r.status_code == 403


def test_login_rate_limit_returns_429(client, user):
    token = csrf_token(client, "/login")  # un fallo no limpia la sesión → token reutilizable
    last = None
    for _ in range(6):
        last = client.post(
            "/login",
            data={"usuario": "user@x.com", "contrasena": "wrong", "csrf_token": token},
            follow_redirects=False,
        )
    assert last.status_code == 429


def test_logout_clears_session(client, user):
    login(client, "user@x.com", "secret6")
    r = client.get("/logout", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/login"
    # tras logout, /admin redirige a login
    r = client.get("/admin", follow_redirects=False)
    assert r.headers["location"] == "/login"


def test_admin_requires_auth(client):
    r = client.get("/admin", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/login"


def test_super_requires_super_admin(client, user):
    login(client, "user@x.com", "secret6")
    r = client.get("/super", follow_redirects=False)
    assert r.headers["location"] == "/login"
