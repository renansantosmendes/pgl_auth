import pytest

from pgl_auth import validation


@pytest.mark.parametrize("registration_number", ["12345", "2021012345"])
def test_registration_number_accepts_five_to_twenty_digits(registration_number):
    assert validation.registration_number_problems(registration_number) == []


@pytest.mark.parametrize("registration_number", ["1234", "", None, "12a45", "1" * 21])
def test_registration_number_rejects_bad_shapes(registration_number):
    assert validation.registration_number_problems(registration_number)


def test_email_must_look_like_an_address():
    assert validation.email_problems("aluno@pucminas.edu.br") == []
    assert validation.email_problems("sem-arroba") == ["Informe um e-mail válido."]


def test_strong_password_passes():
    assert validation.password_problems("Exemplo@2026", "12345") == []


@pytest.mark.parametrize(
    ("senha", "fragment"),
    [
        ("curta@1A", "10 caracteres"),
        ("exemplo@2026", "maiúscula"),
        ("EXEMPLO@2026", "minúscula"),
        ("Exemplo@Abc", "número"),
        ("Exemplo2026", "símbolo"),
        ("Exemplo@12345", "matrícula"),
        ("Password123", "muito comum"),
    ],
)
def test_each_password_rule_is_reported(senha, fragment):
    problems = validation.password_problems(senha, "12345")

    assert any(fragment in problem for problem in problems)


def test_password_longer_than_72_bytes_is_rejected():
    problems = validation.password_problems("Aa1@" + "x" * 80, "12345")

    assert any("72 bytes" in problem for problem in problems)
