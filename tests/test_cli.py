import pytest

from pgl_auth import cli
from tests.test_client import FakeResponse, Script

STRONG = "Exemplo@2026"


@pytest.fixture
def prompts(monkeypatch):
    """Feed getpass and input with scripted answers, in order."""
    answers = {"getpass": [], "input": []}

    def fake_getpass(prompt=""):
        return answers["getpass"].pop(0)

    def fake_input(prompt=""):
        return answers["input"].pop(0)

    monkeypatch.setattr(cli.getpass, "getpass", fake_getpass)
    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr(cli, "TokenCache", lambda: None)
    return answers


def test_default_command_prints_the_token(monkeypatch, prompts, capsys):
    Script(monkeypatch, [FakeResponse(200, {"access_token": "tok-cli", "expires_in": 60})])
    prompts["getpass"].append("minha_senha")

    code = cli.main(["20210001"])

    assert code == 0
    assert capsys.readouterr().out.strip() == "tok-cli"


def test_register_flow_collects_email_and_confirmation(monkeypatch, prompts, capsys):
    script = Script(monkeypatch, [FakeResponse(201, {})])
    prompts["input"].append("aluno@pucminas.edu.br")
    prompts["getpass"].extend([STRONG, STRONG])

    code = cli.main(["20210001", "--register"])

    assert code == 0
    assert script.calls[0]["json"]["email"] == "aluno@pucminas.edu.br"
    assert script.calls[0]["json"]["senha_confirmacao"] == STRONG
    assert "Confirmation link sent" in capsys.readouterr().out


def test_register_shows_the_rules_a_weak_password_breaks(monkeypatch, prompts, capsys):
    Script(monkeypatch, [FakeResponse(201, {})])
    prompts["input"].append("aluno@pucminas.edu.br")
    prompts["getpass"].extend(["fraca", "fraca", "fraca", "fraca", "fraca", "fraca"])

    code = cli.main(["20210001", "--register"])

    assert code == 1
    assert "pelo menos 10 caracteres" in capsys.readouterr().err


def test_register_stops_when_confirmation_differs(monkeypatch, prompts, capsys):
    script = Script(monkeypatch, [])
    prompts["input"].append("aluno@pucminas.edu.br")
    prompts["getpass"].extend([STRONG, "outra"])

    code = cli.main(["20210001", "--register"])

    assert code == 1
    assert script.calls == []
    assert "As senhas não coincidem." in capsys.readouterr().err


def test_forgot_password_sends_the_request(monkeypatch, prompts, capsys):
    script = Script(monkeypatch, [FakeResponse(202, {})])

    code = cli.main(["20210001", "--forgot-password"])

    assert code == 0
    assert script.calls[0]["url"].endswith("/api/password/forgot")
    assert "enviado ao seu e-mail" in capsys.readouterr().out


def test_reset_password_uses_the_code_and_new_password(monkeypatch, prompts):
    script = Script(monkeypatch, [FakeResponse(200, {})])
    prompts["input"].append("123456")
    prompts["getpass"].extend([STRONG, STRONG])

    code = cli.main(["20210001", "--reset-password"])

    assert code == 0
    assert script.calls[0]["json"] == {
        "registration_number": "20210001",
        "codigo": "123456",
        "nova_senha": STRONG,
    }


def test_change_password_logs_in_then_replaces_the_password(monkeypatch, prompts):
    script = Script(
        monkeypatch,
        [
            FakeResponse(200, {"access_token": "tok", "expires_in": 60}),
            FakeResponse(200, {"access_token": "tok-2", "expires_in": 60}),
        ],
    )
    prompts["getpass"].extend(["antiga", STRONG, STRONG])

    code = cli.main(["20210001", "--change-password"])

    assert code == 0
    assert script.calls[1]["url"].endswith("/api/password/change")


def test_logout_without_saved_session_fails(monkeypatch, prompts, capsys):
    code = cli.main(["20210001", "--logout"])

    assert code == 1
    assert "Nenhuma sessão salva" in capsys.readouterr().err


def test_library_errors_are_reported_with_exit_code_one(monkeypatch, prompts, capsys):
    Script(monkeypatch, [FakeResponse(401)])
    prompts["getpass"].append("errada")

    code = cli.main(["20210001"])

    assert code == 1
    assert "Erro:" in capsys.readouterr().err


def test_invalid_registration_number_lists_problems(monkeypatch, prompts, capsys):
    Script(monkeypatch, [])
    prompts["getpass"].append("x")

    code = cli.main(["12", "--forgot-password"])

    assert code == 1
    assert "dígitos" in capsys.readouterr().err


def test_registration_number_is_asked_when_missing(monkeypatch, prompts):
    Script(monkeypatch, [FakeResponse(200, {"access_token": "tok", "expires_in": 60})])
    prompts["input"].append("20210001")
    prompts["getpass"].append("minha_senha")

    assert cli.main([]) == 0


def test_only_one_action_flag_can_be_used():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["20210001", "--register", "--logout"])
