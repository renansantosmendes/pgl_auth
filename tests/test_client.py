"""Testes do cliente HTTP do pgl_auth."""

from __future__ import annotations

import pytest
import requests

from pgl_auth.client import PGLAuthClient
from pgl_auth.exceptions import (
    AlreadyRegisteredError,
    AuthenticationError,
    InactiveAccountError,
    InvalidInputError,
    InvalidResetCodeError,
    PermissionDeniedError,
    PGLAuthError,
    RateLimitedError,
    SessionExpiredError,
)
from pgl_auth.token_cache import TokenCache

STRONG = "Exemplo@2026"
API = "https://example.test"


class FakeResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {}

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


class Script:
    """Replays a list of responses for requests.post/get and records calls."""

    def __init__(self, monkeypatch, responses):
        self.responses = list(responses)
        self.calls = []
        monkeypatch.setattr("pgl_auth.client.requests.post", self._send("POST"))
        monkeypatch.setattr("pgl_auth.client.requests.get", self._send("GET"))
        monkeypatch.setattr("pgl_auth.client.time.sleep", lambda seconds: None)

    def _send(self, method):
        def send(url, **kwargs):
            self.calls.append({"method": method, "url": url, **kwargs})
            outcome = self.responses.pop(0)
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome

        return send


def make_client(**kwargs):
    return PGLAuthClient(base_url=API, **kwargs)


def logged_in_client(monkeypatch, token_cache=None):
    Script(monkeypatch, [FakeResponse(200, {"access_token": "tok-1", "expires_in": 14400})])
    client = make_client(token_cache=token_cache)
    client.login("20210001", "minha_senha")
    return client


def test_login_success_returns_token_and_stores_it(monkeypatch):
    script = Script(monkeypatch, [FakeResponse(200, {"access_token": "token-abc", "expires_in": 14400})])

    client = make_client()
    token = client.login("202100001", "minha_senha")

    assert token == "token-abc"
    assert client.token == "token-abc"
    assert client.auth_header() == {"Authorization": "Bearer token-abc"}
    assert script.calls[0]["json"] == {"registration_number": "202100001", "senha": "minha_senha"}


def test_login_invalid_credentials_raises_authentication_error(monkeypatch):
    Script(monkeypatch, [FakeResponse(401, {"detail": "Matrícula ou senha inválidos."})])

    with pytest.raises(AuthenticationError, match="inválidos"):
        make_client().login("202100001", "senha_errada")


def test_login_inactive_account_raises_inactive_account_error(monkeypatch):
    Script(monkeypatch, [FakeResponse(403)])

    with pytest.raises(InactiveAccountError):
        make_client().login("202100001", "minha_senha")


def test_login_locked_account_raises_rate_limited_error(monkeypatch):
    Script(monkeypatch, [FakeResponse(429, {"detail": "Muitas tentativas."})])

    with pytest.raises(RateLimitedError, match="Muitas"):
        make_client().login("202100001", "minha_senha")


def test_login_saves_token_in_cache_when_configured(monkeypatch, tmp_path):
    cache = TokenCache(tmp_path / "token.json")
    Script(monkeypatch, [FakeResponse(200, {"access_token": "tok", "expires_in": 3600})])

    make_client(token_cache=cache).login("20210001", "minha_senha")

    assert cache.load("20210001") == "tok"


def test_restore_session_loads_a_cached_token(monkeypatch, tmp_path):
    cache = TokenCache(tmp_path / "token.json")
    cache.save("20210001", "cached-token", 3600)

    client = make_client(token_cache=cache)

    assert client.restore_session("20210001") is True
    assert client.auth_header() == {"Authorization": "Bearer cached-token"}
    assert client.restore_session("outra") is False


def test_restore_session_without_cache_returns_false():
    assert make_client().restore_session("20210001") is False


def test_register_success_sends_every_field(monkeypatch):
    script = Script(monkeypatch, [FakeResponse(201, {"registration_number": "202100001"})])

    make_client().register("202100001", "aluno@pucminas.edu.br", STRONG, STRONG)

    assert script.calls[0]["url"] == f"{API}/api/register"
    assert script.calls[0]["json"] == {
        "registration_number": "202100001",
        "email": "aluno@pucminas.edu.br",
        "senha": STRONG,
        "senha_confirmacao": STRONG,
    }


def test_register_checks_every_rule_before_sending(monkeypatch):
    script = Script(monkeypatch, [])

    with pytest.raises(InvalidInputError) as error:
        make_client().register("1234", "sem-arroba", "abc", "xyz")

    assert script.calls == []
    assert len(error.value.problems) >= 4


def test_register_not_enrolled_raises_inactive_account_error(monkeypatch):
    Script(monkeypatch, [FakeResponse(403, {"detail": "Matrícula não encontrada."})])

    with pytest.raises(InactiveAccountError, match="não encontrada"):
        make_client().register("202100001", "aluno@pucminas.edu.br", STRONG, STRONG)


def test_register_already_registered_raises_already_registered_error(monkeypatch):
    Script(monkeypatch, [FakeResponse(409)])

    with pytest.raises(AlreadyRegisteredError):
        make_client().register("202100001", "aluno@pucminas.edu.br", STRONG, STRONG)


def test_register_server_validation_error_lists_problems(monkeypatch):
    Script(
        monkeypatch,
        [FakeResponse(422, {"detail": {"message": "x", "errors": ["Senha fraca."]}})],
    )

    with pytest.raises(InvalidInputError) as error:
        make_client().register("202100001", "aluno@pucminas.edu.br", STRONG, STRONG)

    assert error.value.problems == ["Senha fraca."]


def test_request_password_reset_accepts_202(monkeypatch):
    script = Script(monkeypatch, [FakeResponse(202, {"message": "ok"})])

    make_client().request_password_reset("202100001")

    assert script.calls[0]["url"] == f"{API}/api/password/forgot"


def test_request_password_reset_rejects_bad_registration_number(monkeypatch):
    script = Script(monkeypatch, [])

    with pytest.raises(InvalidInputError):
        make_client().request_password_reset("12")

    assert script.calls == []


def test_reset_password_with_code_success(monkeypatch):
    script = Script(monkeypatch, [FakeResponse(200, {"message": "ok"})])

    make_client().reset_password_with_code("202100001", "123456", STRONG)

    assert script.calls[0]["json"] == {
        "registration_number": "202100001",
        "codigo": "123456",
        "nova_senha": STRONG,
    }


def test_reset_password_with_wrong_code_raises_invalid_reset_code(monkeypatch):
    Script(monkeypatch, [FakeResponse(400, {"detail": "Código inválido ou expirado."})])

    with pytest.raises(InvalidResetCodeError):
        make_client().reset_password_with_code("202100001", "000000", STRONG)


def test_reset_password_with_code_checks_strength_locally(monkeypatch):
    script = Script(monkeypatch, [])

    with pytest.raises(InvalidInputError):
        make_client().reset_password_with_code("202100001", "123456", "fraca")

    assert script.calls == []


def test_change_password_requires_a_session(monkeypatch):
    Script(monkeypatch, [])

    with pytest.raises(SessionExpiredError):
        make_client().change_password("atual", STRONG)


def test_change_password_replaces_the_token(monkeypatch):
    client = logged_in_client(monkeypatch)
    script = Script(monkeypatch, [FakeResponse(200, {"access_token": "tok-2", "expires_in": 14400})])

    client.change_password("minha_senha", STRONG)

    assert client.token == "tok-2"
    assert script.calls[0]["headers"] == {"Authorization": "Bearer tok-1"}


def test_change_password_wrong_current_password_raises_authentication_error(monkeypatch):
    client = logged_in_client(monkeypatch)
    Script(monkeypatch, [FakeResponse(401, {"detail": "Senha atual inválida."})])

    with pytest.raises(AuthenticationError):
        client.change_password("errada", STRONG)


def test_change_password_revoked_token_raises_session_expired(monkeypatch):
    client = logged_in_client(monkeypatch)
    Script(monkeypatch, [FakeResponse(401, {"detail": "Sessão inválida. Faça login novamente."})])

    with pytest.raises(SessionExpiredError):
        client.change_password("minha_senha", STRONG)


def test_change_password_checks_strength_locally(monkeypatch):
    client = logged_in_client(monkeypatch)
    script = Script(monkeypatch, [])

    with pytest.raises(InvalidInputError):
        client.change_password("minha_senha", "fraca")

    assert script.calls == []


def test_logout_revokes_and_forgets_the_session(monkeypatch, tmp_path):
    cache = TokenCache(tmp_path / "token.json")
    client = logged_in_client(monkeypatch, token_cache=cache)
    script = Script(monkeypatch, [FakeResponse(200, {"message": "ok"})])

    client.logout()

    assert client.token is None
    assert cache.load("20210001") is None
    assert script.calls[0]["url"] == f"{API}/api/logout"


def test_logout_without_session_raises_session_expired(monkeypatch):
    Script(monkeypatch, [])

    with pytest.raises(SessionExpiredError):
        make_client().logout()


def test_list_students_returns_roster_rows(monkeypatch):
    client = logged_in_client(monkeypatch)
    rows = [{"registration_number": "1", "has_password": True}]
    Script(monkeypatch, [FakeResponse(200, {"students": rows})])

    assert client.list_students() == rows


def test_list_students_for_a_student_raises_permission_denied(monkeypatch):
    client = logged_in_client(monkeypatch)
    Script(monkeypatch, [FakeResponse(403, {"detail": "Apenas professores."})])

    with pytest.raises(PermissionDeniedError):
        client.list_students()


def test_set_student_status_for_student_without_password_raises(monkeypatch):
    client = logged_in_client(monkeypatch)
    Script(monkeypatch, [FakeResponse(404, {"detail": "Sem senha."})])

    with pytest.raises(PGLAuthError, match="Sem senha"):
        client.set_student_status("1", False)


def test_set_student_status_success(monkeypatch):
    client = logged_in_client(monkeypatch)
    script = Script(monkeypatch, [FakeResponse(200, {"is_active": False})])

    client.set_student_status("1", False)

    assert script.calls[0]["json"] == {"is_active": False}
    assert script.calls[0]["url"] == f"{API}/api/professor/students/1/status"


def test_send_invitations_returns_sent_and_skipped(monkeypatch):
    client = logged_in_client(monkeypatch)
    body = {"sent": ["1"], "skipped": [{"registration_number": "2", "reason": "x"}]}
    Script(monkeypatch, [FakeResponse(200, body)])

    assert client.send_invitations(["1", "2"]) == body


def test_send_invitations_with_empty_list_raises_invalid_input(monkeypatch):
    client = logged_in_client(monkeypatch)
    Script(monkeypatch, [FakeResponse(422, {"detail": {"errors": ["lista vazia"]}})])

    with pytest.raises(InvalidInputError):
        client.send_invitations([])


def test_reset_student_password_success(monkeypatch):
    client = logged_in_client(monkeypatch)
    script = Script(monkeypatch, [FakeResponse(200, {"message": "ok"})])

    client.reset_student_password("1", STRONG)

    assert script.calls[0]["json"] == {"registration_number": "1", "new_senha": STRONG}


def test_connection_errors_are_retried_then_succeed(monkeypatch):
    script = Script(
        monkeypatch,
        [
            requests.ConnectionError("reset"),
            FakeResponse(200, {"access_token": "tok", "expires_in": 60}),
        ],
    )

    assert make_client().login("20210001", "minha_senha") == "tok"
    assert len(script.calls) == 2


def test_gateway_errors_are_retried(monkeypatch):
    script = Script(
        monkeypatch,
        [FakeResponse(503), FakeResponse(200, {"access_token": "tok", "expires_in": 60})],
    )

    make_client().login("20210001", "minha_senha")

    assert len(script.calls) == 2


def test_connection_errors_give_up_after_three_attempts(monkeypatch):
    script = Script(monkeypatch, [requests.ConnectionError("down")] * 3)

    with pytest.raises(PGLAuthError, match="Falha ao contatar"):
        make_client().login("20210001", "minha_senha")

    assert len(script.calls) == 3


def test_auth_header_without_login_raises_error():
    with pytest.raises(PGLAuthError):
        make_client().auth_header()


def test_endpoints_follow_the_base_url_by_default(monkeypatch):
    monkeypatch.delenv("PGL_AUTH_BASE_URL", raising=False)
    monkeypatch.delenv("PGL_AUTH_API_URL", raising=False)
    monkeypatch.delenv("PGL_AUTH_REGISTER_URL", raising=False)

    client = PGLAuthClient()

    assert client.api_url == "https://pgl-auth-server.vercel.app/api/login"
    assert client.register_url == "https://pgl-auth-server.vercel.app/api/register"
