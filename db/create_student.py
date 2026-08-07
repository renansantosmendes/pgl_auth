"""Cria ou atualiza a senha de um aluno em pgl_auth.students.

Uso:
    python db/create_student.py <matricula> [--inactive]
A senha é solicitada de forma oculta no terminal.
"""
from __future__ import annotations

import argparse
import getpass
import os

import bcrypt
import psycopg2
from dotenv import load_dotenv

load_dotenv()

UPSERT_SQL = """
INSERT INTO pgl_auth.students (matricula, password_hash, is_active)
VALUES (%s, %s, %s)
ON CONFLICT (matricula)
DO UPDATE SET password_hash = EXCLUDED.password_hash, is_active = EXCLUDED.is_active;
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Cria/atualiza um aluno no pgl_auth.")
    parser.add_argument("matricula")
    parser.add_argument("--inactive", action="store_true", help="Cria o aluno já como inativo")
    args = parser.parse_args()

    senha = getpass.getpass("Senha: ")
    confirmacao = getpass.getpass("Confirme a senha: ")
    if senha != confirmacao:
        raise SystemExit("As senhas não conferem.")

    password_hash = bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    database_url = os.environ["NEON_DATABASE_URL"]

    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(UPSERT_SQL, (args.matricula, password_hash, not args.inactive))
        conn.commit()

    print(f"Aluno {args.matricula} salvo com sucesso.")


if __name__ == "__main__":
    main()
