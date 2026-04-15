from __future__ import annotations

from .conftest import auth_headers


def test_chat_endpoint_requires_authentication(client) -> None:
    response = client.post("/chatkit", content=b"{}")
    assert response.status_code == 401


def test_chat_endpoint_rejects_invalid_token(client) -> None:
    response = client.post(
        "/chatkit",
        headers={"Authorization": "Bearer wrong-token"},
        content=b"{}",
    )
    assert response.status_code == 401


def test_chat_endpoint_allows_authenticated_user(client) -> None:
    response = client.post("/chatkit", headers=auth_headers(), content=b"{}")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_suggestions_require_authentication(client) -> None:
    response = client.get("/chatkit/suggestions")
    assert response.status_code == 401


def test_suggestions_allow_authenticated_user(client) -> None:
    response = client.get("/chatkit/suggestions", headers=auth_headers())
    assert response.status_code == 200
    payload = response.json()
    assert payload["hasHistory"] is False
    assert payload["suggestions"] == []
