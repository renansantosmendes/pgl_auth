from __future__ import annotations

import argparse
import getpass
import sys

from .exceptions import PGLAuthError


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="pgl-auth",
        description="Cadastra a senha do aluno ou autentica e imprime o token de acesso.",
    )
    parser.add_argument("matricula", nargs="?", help="Número de matrícula do aluno")
    parser.add_argument(
        "--register",
        action="store_true",
        help="Cadastra a senha pela primeira vez, em vez de fazer login",
    )
    parser.add_argument("--api-url", dest="api_url", default=None, help="URL da API de login")
    parser.add_argument(
        "--register-url", dest="register_url", default=None, help="URL da API de cadastro"
    )
    args = parser.parse_args()

    matricula = args.matricula or input("Matrícula: ")

    from .client import PGLAuthClient

    client = PGLAuthClient(api_url=args.api_url, register_url=args.register_url)

    if args.register:
        senha = getpass.getpass("Nova senha: ")
        confirmar = getpass.getpass("Confirmar senha: ")
        if senha != confirmar:
            print("Erro: as senhas não coincidem.", file=sys.stderr)
            return 1

        try:
            client.register(matricula, senha)
        except PGLAuthError as exc:
            print(f"Erro: {exc}", file=sys.stderr)
            return 1

        print("Senha cadastrada com sucesso. Rode `pgl-auth` (sem --register) para logar.")
        return 0

    senha = getpass.getpass("Senha: ")
    try:
        token = client.login(matricula, senha)
    except PGLAuthError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
