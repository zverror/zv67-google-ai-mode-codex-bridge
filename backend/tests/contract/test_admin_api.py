"""Administrative API authentication, CSRF and CRUD tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from zv67.config import Settings
from zv67.main import create_app

PASSWORD = "correct-horse-battery"


def setup_admin(client: TestClient) -> str:
    response = client.post("/admin/api/auth/setup", json={"password": PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"]


def test_admin_endpoints_require_authentication(client):
    response = client.get("/admin/api/overview")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_setup_login_and_status(client):
    status = client.get("/admin/api/auth/status").json()
    assert status == {"configured": False, "authenticated": False, "csrf_token": None}

    short = client.post("/admin/api/auth/setup", json={"password": "too-short"})
    assert short.status_code == 400

    csrf = setup_admin(client)
    status = client.get("/admin/api/auth/status").json()
    assert status["configured"] is True
    assert status["authenticated"] is True
    assert status["csrf_token"] == csrf

    client.post("/admin/api/auth/logout")
    assert client.get("/admin/api/overview").status_code == 401

    wrong = client.post("/admin/api/auth/login", json={"password": "wrong-password"})
    assert wrong.status_code == 401
    login = client.post("/admin/api/auth/login", json={"password": PASSWORD})
    assert login.status_code == 200
    assert client.get("/admin/api/auth/status").json()["csrf_token"] == login.json()["csrf_token"]


def test_login_rate_limit_after_five_failures(tmp_path):
    settings = Settings(
        api_key=None,
        database_path=tmp_path / "zv67.sqlite3",
        data_dir=tmp_path,
        master_key_store="file",
    )
    with TestClient(create_app(settings)) as client:
        client.post("/admin/api/auth/setup", json={"password": PASSWORD})
        client.post("/admin/api/auth/logout")
        for _ in range(5):
            client.post("/admin/api/auth/login", json={"password": "wrong-password"})
        response = client.post("/admin/api/auth/login", json={"password": PASSWORD})
    assert response.status_code == 429


def test_mutations_require_csrf_token(client):
    csrf = setup_admin(client)
    payload = {"display_name": "Work"}

    missing = client.post("/admin/api/accounts", json=payload)
    assert missing.status_code == 403
    assert missing.json()["error"]["code"] == "csrf_failed"

    created = client.post(
        "/admin/api/accounts",
        json=payload,
        headers={"X-ZV67-CSRF": csrf},
    )
    assert created.status_code == 200
    assert created.json()["display_name"] == "Work"


def test_account_crud_and_credentials_are_never_returned(client):
    csrf = setup_admin(client)
    headers = {"X-ZV67-CSRF": csrf}
    created = client.post(
        "/admin/api/accounts",
        json={"display_name": "Google 1", "routing_weight": 50},
        headers=headers,
    ).json()
    account_id = created["id"]
    assert created["has_credentials"] is False

    stored = client.put(
        f"/admin/api/accounts/{account_id}/credentials",
        json={
            "credentials_text": (
                '[{"domain": ".google.com", "name": "SID", "value": "secret-value"}]'
            )
        },
        headers=headers,
    )
    assert stored.status_code == 200
    assert "secret-value" not in stored.text

    netscape = client.put(
        f"/admin/api/accounts/{account_id}/credentials",
        json={
            "credentials_text": (
                "#HttpOnly_.google.com\tTRUE\t/\tTRUE\t1824327060\t__Secure-1PSID\tvalue-2"
            )
        },
        headers=headers,
    )
    assert netscape.status_code == 200
    assert "value-2" not in netscape.text

    invalid = client.put(
        f"/admin/api/accounts/{account_id}/credentials",
        json={"credentials_text": "not a cookie format"},
        headers=headers,
    )
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "invalid_credentials"

    patched = client.patch(
        f"/admin/api/accounts/{account_id}",
        json={"concurrency_limit": 3, "enabled": False},
        headers=headers,
    )
    assert patched.status_code == 200
    assert patched.json()["concurrency_limit"] == 3
    assert patched.json()["enabled"] is False

    listed = client.get("/admin/api/accounts").json()
    assert listed[0]["has_credentials"] is True
    assert "secret-value" not in str(listed)

    deleted = client.delete(f"/admin/api/accounts/{account_id}", headers=headers)
    assert deleted.status_code == 200
    assert client.get("/admin/api/accounts").json() == []


def test_settings_update_is_runtime_and_persistent(client, app):
    csrf = setup_admin(client)
    response = client.put(
        "/admin/api/settings",
        json={"routing_strategy": "least_busy"},
        headers={"X-ZV67-CSRF": csrf},
    )

    assert response.status_code == 200
    assert app.state.routing_strategy == "least_busy"
    assert client.get("/admin/api/settings").json()["routing_strategy"] == "least_busy"


def test_overview_requests_sessions_and_audit(client, app):
    csrf = setup_admin(client)
    client.post(
        "/v1/chat/completions",
        json={"model": "zv67-mock", "messages": [{"role": "user", "content": "hello"}]},
    )

    overview = client.get("/admin/api/overview")
    assert overview.status_code == 200
    assert overview.json()["summary"]["requests"] == 1

    requests = client.get("/admin/api/requests").json()
    assert len(requests) == 1
    assert requests[0]["status"] == "SUCCESS"

    sessions = client.get("/admin/api/sessions").json()
    assert len(sessions) == 1
    deleted = client.delete(
        f"/admin/api/sessions/{sessions[0]['id']}",
        headers={"X-ZV67-CSRF": csrf},
    )
    assert deleted.status_code == 200

    audit = client.get("/admin/api/audit").json()
    actions = {entry["action"] for entry in audit}
    assert "admin.setup" in actions
    assert "session.deleted" in actions


def test_models_and_system_endpoints(client):
    setup_admin(client)
    models = client.get("/admin/api/models").json()
    assert models[0]["id"] == "zv67-mock"
    assert models[0]["capabilities"]["tool_calling"] == "UNSUPPORTED"

    system = client.get("/admin/api/system").json()
    assert system["mock"] is True
    assert system["provider"] == "mock"

