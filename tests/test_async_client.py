import asyncio

import pytest

from pgl_auth.async_client import AsyncPGLAuthClient
from pgl_auth.exceptions import AuthenticationError, InvalidInputError

from tests.test_client import FakeResponse, Script

API = "https://example.test"


def test_async_login_returns_the_token(monkeypatch):
    Script(monkeypatch, [FakeResponse(200, {"access_token": "tok-async", "expires_in": 60})])

    client = AsyncPGLAuthClient(base_url=API)

    token = asyncio.run(client.login("20210001", "minha_senha"))

    assert token == "tok-async"
    assert client.token == "tok-async"


def test_async_errors_are_the_same_as_the_sync_client(monkeypatch):
    Script(monkeypatch, [FakeResponse(401)])

    client = AsyncPGLAuthClient(base_url=API)

    with pytest.raises(AuthenticationError):
        asyncio.run(client.login("20210001", "errada"))


def test_async_register_checks_rules_before_sending(monkeypatch):
    script = Script(monkeypatch, [])

    client = AsyncPGLAuthClient(base_url=API)

    with pytest.raises(InvalidInputError):
        asyncio.run(client.register("12", "x", "abc", "abc"))

    assert script.calls == []


def test_async_list_students_round_trip(monkeypatch):
    Script(
        monkeypatch,
        [
            FakeResponse(200, {"access_token": "tok", "expires_in": 60}),
            FakeResponse(200, {"students": [{"registration_number": "1"}]}),
        ],
    )

    async def scenario():
        client = AsyncPGLAuthClient(base_url=API)
        await client.login("20210001", "minha_senha")
        return await client.list_students()

    assert asyncio.run(scenario()) == [{"registration_number": "1"}]
