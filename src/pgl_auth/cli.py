from __future__ import annotations

import argparse
import getpass
import sys
from typing import Optional

from . import validation
from .client import PGLAuthClient
from .exceptions import InvalidInputError, PGLAuthError
from .token_cache import TokenCache

MAX_PASSWORD_ATTEMPTS = 3


def build_parser() -> argparse.ArgumentParser:
    """Create the parser with every option of the command line tool.

    Returns
    -------
    argparse.ArgumentParser
        Parser that reads the arguments of ``pgl-auth``.
    """
    parser = argparse.ArgumentParser(
        prog="pgl-auth",
        description="Login, cadastro e gestão de senha do pgl_auth.",
    )
    parser.add_argument("registration_number", nargs="?", help="Número de matrícula")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--register", action="store_true", help="Cria a senha pela primeira vez")
    actions.add_argument(
        "--change-password", action="store_true", help="Troca a senha informando a atual"
    )
    actions.add_argument(
        "--forgot-password", action="store_true", help="Envia um código para o e-mail institucional"
    )
    actions.add_argument(
        "--reset-password", action="store_true", help="Redefine a senha com o código recebido"
    )
    actions.add_argument("--logout", action="store_true", help="Encerra a sessão salva")
    parser.add_argument(
        "--remember",
        action="store_true",
        help="Salva o token em ~/.pgl_auth/token.json para os próximos comandos",
    )
    parser.add_argument("--base-url", dest="base_url", default=None, help="URL base da API")
    parser.add_argument("--api-url", dest="api_url", default=None, help="URL do login")
    parser.add_argument("--register-url", dest="register_url", default=None, help="URL do cadastro")
    return parser


def prompt_new_password(registration_number: str, label: str) -> Optional[str]:
    """Ask for a new password, showing the rules that it breaks.

    The password is checked as it is typed. The student may try again up to
    ``MAX_PASSWORD_ATTEMPTS`` times.

    Parameters
    ----------
    registration_number : str
        Registration number, which must not be part of the password.
    label : str
        Text shown before the prompt.

    Returns
    -------
    str | None
        Password that follows the rules, or None when every attempt failed.
    """
    for _ in range(MAX_PASSWORD_ATTEMPTS):
        senha = getpass.getpass(f"{label}: ")
        problems = validation.password_problems(senha, registration_number)
        if not problems:
            return senha
        print("A senha ainda não atende às regras:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
    return None


def prompt_confirmation() -> str:
    """Ask the student to type the new password again.

    Returns
    -------
    str
        Text typed in the confirmation prompt.
    """
    return getpass.getpass("Confirme a senha: ")


def run_register(client: PGLAuthClient, registration_number: str) -> int:
    """Create the password of an enrolled student.

    Parameters
    ----------
    client : PGLAuthClient
        Client that sends the request.
    registration_number : str
        Registration number of the student.

    Returns
    -------
    int
        Exit code of the command.
    """
    email = input("E-mail institucional: ").strip()
    senha = prompt_new_password(registration_number, "Nova senha")
    if senha is None:
        return _fail("Nenhuma senha válida foi informada.")
    confirmation = prompt_confirmation()
    client.register(registration_number, email, senha, confirmation)
    print("Senha cadastrada com sucesso. Rode `pgl-auth` para entrar.")
    return 0


def run_forgot_password(client: PGLAuthClient, registration_number: str) -> int:
    """Ask the server to send a reset code to the student's e-mail.

    Parameters
    ----------
    client : PGLAuthClient
        Client that sends the request.
    registration_number : str
        Registration number of the student.

    Returns
    -------
    int
        Exit code of the command.
    """
    client.request_password_reset(registration_number)
    print("Se a matrícula estiver ativa, o código foi enviado ao seu e-mail institucional.")
    print("Use `pgl-auth <matrícula> --reset-password` para definir a nova senha.")
    return 0


def run_reset_password(client: PGLAuthClient, registration_number: str) -> int:
    """Set a new password using the code received by e-mail.

    Parameters
    ----------
    client : PGLAuthClient
        Client that sends the request.
    registration_number : str
        Registration number of the student.

    Returns
    -------
    int
        Exit code of the command.
    """
    code = input("Código recebido por e-mail: ").strip()
    senha = prompt_new_password(registration_number, "Nova senha")
    if senha is None:
        return _fail("Nenhuma senha válida foi informada.")
    if prompt_confirmation() != senha:
        return _fail("As senhas não coincidem.")
    client.reset_password_with_code(registration_number, code, senha)
    print("Senha redefinida com sucesso. Rode `pgl-auth` para entrar.")
    return 0


def run_change_password(client: PGLAuthClient, registration_number: str) -> int:
    """Replace the password after confirming the current one.

    Parameters
    ----------
    client : PGLAuthClient
        Client that sends the requests.
    registration_number : str
        Registration number of the student.

    Returns
    -------
    int
        Exit code of the command.
    """
    current = getpass.getpass("Senha atual: ")
    client.login(registration_number, current)
    senha = prompt_new_password(registration_number, "Nova senha")
    if senha is None:
        return _fail("Nenhuma senha válida foi informada.")
    if prompt_confirmation() != senha:
        return _fail("As senhas não coincidem.")
    client.change_password(current, senha)
    print("Senha alterada com sucesso. A sessão continua aberta neste computador.")
    return 0


def run_logout(client: PGLAuthClient, registration_number: str) -> int:
    """Close the session saved in the token cache.

    Parameters
    ----------
    client : PGLAuthClient
        Client that holds the cache.
    registration_number : str
        Registration number whose session is closed.

    Returns
    -------
    int
        Exit code of the command.
    """
    if not client.restore_session(registration_number):
        return _fail("Nenhuma sessão salva para essa matrícula.")
    client.logout()
    print("Sessão encerrada.")
    return 0


def run_login(client: PGLAuthClient, registration_number: str) -> int:
    """Check the password and print the access token.

    Parameters
    ----------
    client : PGLAuthClient
        Client that sends the request.
    registration_number : str
        Registration number of the student.

    Returns
    -------
    int
        Exit code of the command.
    """
    senha = getpass.getpass("Senha: ")
    print(client.login(registration_number, senha))
    return 0


def _fail(message: str) -> int:
    """Print an error message and return the failure exit code.

    Parameters
    ----------
    message : str
        Message shown to the student on the error output.

    Returns
    -------
    int
        Always 1.
    """
    print(f"Erro: {message}", file=sys.stderr)
    return 1


def main(argv: Optional[list] = None) -> int:
    """Run the command line tool.

    Parameters
    ----------
    argv : list[str] | None
        Arguments without the program name. Defaults to ``sys.argv``.

    Returns
    -------
    int
        0 on success, 1 on any error reported by the library.
    """
    args = build_parser().parse_args(argv)
    registration_number = args.registration_number or input("Matrícula: ").strip()
    cache = TokenCache() if args.remember or args.logout else None
    client = PGLAuthClient(
        api_url=args.api_url,
        register_url=args.register_url,
        base_url=args.base_url,
        token_cache=cache,
    )

    handlers = {
        "register": run_register,
        "forgot_password": run_forgot_password,
        "reset_password": run_reset_password,
        "change_password": run_change_password,
        "logout": run_logout,
    }
    action = next(
        (name for name in handlers if getattr(args, name, False)),
        None,
    )
    try:
        if action is None:
            return run_login(client, registration_number)
        return handlers[action](client, registration_number)
    except InvalidInputError as exc:
        print("Erro: os dados informados não atendem às regras:", file=sys.stderr)
        for problem in exc.problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    except PGLAuthError as exc:
        return _fail(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
