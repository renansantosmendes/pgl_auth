"""Testes do pacote pgl_auth (cliente HTTP usado pelos alunos)."""
from __future__ import annotations

import pytest

from pgl_auth.client import PGLAuthClient
from pgl_auth.exceptions import AuthenticationError, InactiveAccountError


class FakeResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {}

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(f"status {self.status_code}")


def test_login_success_returns_token_and_stores_it(monkeypatch):
    def fake_post(url, json, timeout):
        assert json == {"matricula": "202100001", "senha": "minha_senha"}
        return FakeResponse(200, {"access_token": "token-abc", "expires_in": 14400})

    monkeypatch.setattr("pgl_auth.client.requests.post", fake_post)

    client = PGLAuthClient(api_url="https://example.test/api/login")
    token = client.login("202100001", "minha_senha")

    assert token == "token-abc"
    assert client.token == "token-abc"
    assert client.auth_header() == {"Authorization": "Bearer token-abc"}


def test_login_invalid_credentials_raises_authentication_error(monkeypatch):
    monkeypatch.setattr(
        "pgl_auth.client.requests.post",
        lambda url, json, timeout: FakeResponse(401),
    )

    client = PGLAuthClient(api_url="https://example.test/api/login")
    with pytest.raises(AuthenticationError):
        client.login("202100001", "senha_errada")


def test_login_inactive_account_raises_inactive_account_error(monkeypatch):
    monkeypatch.setattr(
        "pgl_auth.client.requests.post",
        lambda url, json, timeout: FakeResponse(403),
    )

    client = PGLAuthClient(api_url="https://example.test/api/login")
    with pytest.raises(InactiveAccountError):
        client.login("202100001", "minha_senha")


def test_auth_header_without_login_raises_error():
    client = PGLAuthClient(api_url="https://example.test/api/login")
    from pgl_auth.exceptions import PGLAuthError

    with pytest.raises(PGLAuthError):
        client.auth_header()
