"""Short-lived path-scoped download tokens (POST /api/auth/download-token + ?dl=)."""
from __future__ import annotations

import hashlib
import hmac
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

TOKEN = "ci-test-token-abc123"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
PATH = "/api/events"


@pytest.fixture
def client(monkeypatch):
    mock_settings = MagicMock()
    mock_settings.AUTH_TOKEN = TOKEN
    monkeypatch.setattr("backend.core.auth.settings", mock_settings)
    from backend.main import create_app
    app = create_app()
    app.state.stores = MagicMock()
    app.state.ollama = MagicMock()
    return TestClient(app, raise_server_exceptions=False)


def _issue(client, path=PATH):
    resp = client.post("/api/auth/download-token", json={"path": path}, headers=AUTH)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_issue_requires_auth(client):
    assert client.post("/api/auth/download-token", json={"path": PATH}).status_code == 401


def test_issue_contract_shape(client, monkeypatch):
    monkeypatch.setattr("backend.core.auth._now", lambda: 1_000_000)
    data = _issue(client, PATH + "?format=csv")
    assert data["expires_in"] == 120
    exp, sig = data["token"].split(".")
    assert exp == "1000120"
    expected = hmac.new(TOKEN.encode(), f"{PATH}|1000120".encode(), hashlib.sha256).hexdigest()
    assert sig == expected  # query string stripped before signing


@pytest.mark.parametrize("bad", ["/health", "api/events", "https://evil/api/x", "/apix"])
def test_issue_rejects_non_api_path(client, bad):
    resp = client.post("/api/auth/download-token", json={"path": bad}, headers=AUTH)
    assert resp.status_code == 400


def test_dl_on_matching_path_passes_auth(client):
    tok = _issue(client)["token"]
    assert client.get(f"{PATH}?dl={tok}").status_code != 401


def test_dl_on_wrong_path_401(client):
    tok = _issue(client)["token"]
    assert client.get(f"/api/detect?dl={tok}").status_code == 401


def test_dl_expired_401(client, monkeypatch):
    monkeypatch.setattr("backend.core.auth._now", lambda: 1_000_000)
    tok = _issue(client)["token"]
    monkeypatch.setattr("backend.core.auth._now", lambda: 1_000_121)
    assert client.get(f"{PATH}?dl={tok}").status_code == 401


def test_dl_tampered_sig_401(client):
    exp, sig = _issue(client)["token"].split(".")
    flipped = ("0" if sig[0] != "0" else "1") + sig[1:]
    assert client.get(f"{PATH}?dl={exp}.{flipped}").status_code == 401


def test_dl_tampered_exp_401(client):
    exp, sig = _issue(client)["token"].split(".")
    assert client.get(f"{PATH}?dl={int(exp) + 1}.{sig}").status_code == 401


@pytest.mark.parametrize("junk", ["", "abc", "123", ".abc", "12.éé"])
def test_dl_malformed_401(client, junk):
    assert client.get(f"{PATH}", params={"dl": junk}).status_code == 401


def test_dl_not_accepted_for_post(client):
    tok = _issue(client, "/api/feedback")["token"]
    resp = client.post(f"/api/feedback?dl={tok}", json={"detection_id": "d", "verdict": "TP"})
    assert resp.status_code == 401


def test_legacy_query_token_still_works(client):
    assert client.get(f"{PATH}?token={TOKEN}").status_code != 401
