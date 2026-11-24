"""Login, sessions, permissions and CSRF, against a fake database."""
import pytest

import Passwords
import AgricultureFoodSupplyChainV1Server as server

FULL_ROLE = (1, "Admin", 1, 1, 1, 1, 1, 1, 1)
NO_BUYER_ROLE = (2, "Clerk", 1, 1, 1, 0, 1, 1, 1)  # canBuyer = 0


@pytest.fixture
def client():
    server.app.config["TESTING"] = True
    return server.app.test_client()


def make_handler(stored_password, role=FULL_ROLE, user_active=True):
    def handler(sql, params):
        if "FROM Users u LEFT JOIN Role" in sql:  # login lookup
            return [(1, stored_password, role[0])] if user_active else []
        if "FROM Users u JOIN Role" in sql:       # per-request user + role
            return [(1,) + role] if user_active else []
        if sql.startswith("SELECT password FROM Users"):
            return [(stored_password,)]
        return []
    return handler


def csrf(client):
    client.get("/")
    with client.session_transaction() as sess:
        return sess["csrf_token"]


def login(client, password="pw"):
    return client.post("/processLogin", data={"emailid": "a@b.c", "password": password, "csrf_token": csrf(client)})


# --- CSRF -------------------------------------------------------------------

def test_login_page_contains_a_csrf_token(client):
    page = client.get("/").get_data(as_text=True)
    with client.session_transaction() as sess:
        assert sess["csrf_token"] in page


def test_post_without_csrf_token_is_rejected(client, fake_db):
    response = client.post("/processLogin", data={"emailid": "a@b.c", "password": "pw"})
    assert response.status_code == 400
    assert fake_db.executed == []


def test_post_with_wrong_csrf_token_is_rejected(client, fake_db):
    csrf(client)
    response = client.post("/processLogin", data={"emailid": "a@b.c", "password": "pw", "csrf_token": "forged"})
    assert response.status_code == 400


# --- Login and sessions ----------------------------------------------------

def test_protected_pages_redirect_to_login_when_logged_out(client, fake_db):
    for path in ("/Dashboard", "/BlockChainReport", "/BlockChainGeneration", "/UsersListing"):
        response = client.get(path)
        assert response.status_code == 302 and response.location.endswith("/"), path


def test_protected_post_redirects_to_login_when_logged_out(client, fake_db):
    response = client.post("/ProcessUsersOperation", data={"operation": "Delete", "userID": "1", "csrf_token": csrf(client)})
    assert response.status_code == 302 and response.location.endswith("/")
    assert not [sql for sql, _ in fake_db.executed if sql.startswith("DELETE")]


def test_login_with_hashed_password(client, fake_db):
    fake_db.handler = make_handler(Passwords.hash_password("pw"))
    response = login(client)
    assert response.status_code == 302 and response.location.endswith("/Dashboard")
    assert client.get("/Dashboard").status_code == 200


def test_wrong_password_is_rejected(client, fake_db):
    fake_db.handler = make_handler(Passwords.hash_password("pw"))
    response = login(client, password="nope")
    assert "Invalid Credentials" in response.get_data(as_text=True)
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_login_query_is_parameterised(client, fake_db):
    fake_db.handler = make_handler(Passwords.hash_password("pw"))
    client.post("/processLogin", data={"emailid": "x' OR '1'='1", "password": "x' OR '1'='1", "csrf_token": csrf(client)})
    sql, params = next((sql, p) for sql, p in fake_db.executed if "FROM Users u LEFT JOIN Role" in sql)
    assert "OR '1'='1" not in sql and params == ("x' OR '1'='1",)


def test_legacy_plain_text_password_is_upgraded_on_login(client, fake_db):
    fake_db.handler = make_handler("pw")
    assert login(client).status_code == 302
    sql, params = next((sql, p) for sql, p in fake_db.executed if sql.startswith("UPDATE Users SET password"))
    assert Passwords.is_hashed(params[0]) and Passwords.verify(params[0], "pw")


def test_sessions_are_per_browser(client, fake_db):
    fake_db.handler = make_handler(Passwords.hash_password("pw"))
    login(client)
    other_browser = server.app.test_client()
    assert other_browser.get("/Dashboard").status_code == 302


def test_logout_ends_the_session(client, fake_db):
    fake_db.handler = make_handler(Passwords.hash_password("pw"))
    login(client)
    client.get("/Logout")
    assert client.get("/Dashboard").status_code == 302


def test_deactivated_user_is_logged_out_on_next_request(client, fake_db):
    fake_db.handler = make_handler(Passwords.hash_password("pw"))
    login(client)
    fake_db.handler = make_handler(Passwords.hash_password("pw"), user_active=False)
    assert client.get("/Dashboard").status_code == 302


# --- Permissions -----------------------------------------------------------

def test_missing_permission_shows_information_page(client, fake_db):
    fake_db.handler = make_handler(Passwords.hash_password("pw"), role=NO_BUYER_ROLE)
    login(client)
    response = client.get("/BuyerListing")
    assert response.status_code == 302 and response.location.endswith("/Information")
    page = client.get("/Information").get_data(as_text=True)
    assert "Permission to Access Buyer" in page


def test_change_password_stores_a_hash(client, fake_db):
    fake_db.handler = make_handler(Passwords.hash_password("pw"))
    login(client)
    response = client.post("/ProcessChangePassword", data={
        "oldPassword": "pw", "newPassword": "new-pw", "confirmPassword": "new-pw", "csrf_token": csrf(client)})
    assert "Password Changed Successfully" in response.get_data(as_text=True)
    sql, params = next((sql, p) for sql, p in fake_db.executed if sql.startswith("UPDATE Users SET password"))
    assert Passwords.verify(params[0], "new-pw")
