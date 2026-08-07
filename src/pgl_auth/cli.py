from __future__ import annotations

import argparse
import getpass
import sys

from .exceptions import PGLAuthError


def main() -> int:
    parser = argparse.ArgumentParser(prog="pgl-auth", description="Autentica o aluno e imprime o token de acesso.")
    parser.add_argument("matricula", nargs="?", help="Número de matrícula do aluno")
    parser.add_argument("--api-url", dest="api_url", default=None, help="URL da API de autenticação")
    args = parser.parse_args()

    matricula = args.matricula or input("Matrícula: ")
    senha = getpass.getpass("Senha: ")

    from .client import PGLAuthClient

    client = PGLAuthClient(api_url=args.api_url)
    try:
        token = client.login(matricula, senha)
    except PGLAuthError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
