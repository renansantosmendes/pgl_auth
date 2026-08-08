"""Cria ou atualiza a senha de um aluno em pgl_auth.students.

Só é permitido criar/atualizar a senha se a matrícula já existir e estiver
ativa em pgl_proxy.students. Se a matrícula já tiver um registro em
pgl_auth.students, ele é sobrescrito (senha e is_active atualizados).

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

CHECK_PROXY_SQL = "SELECT is_active FROM pgl_proxy.students WHERE matricula = %s;"

UPSERT_SQL = """
INSERT INTO pgl_auth.students (matricula, password_hash, is_active)
VALUES (%s, %s, %s)
ON CONFLICT (matricula)
DO UPDATE SET password_hash = EXCLUDED.password_hash, is_active = EXCLUDED.is_active;
"""


class StudentNotEligible(Exception):
    """Levantada quando a matrícula não pode ter uma senha criada/atualizada."""


def get_proxy_active_status(cur, matricula: str) -> bool | None:
    """Retorna is_active do aluno em pgl_proxy.students, ou None se não existir."""
    cur.execute(CHECK_PROXY_SQL, (matricula,))
    row = cur.fetchone()
    return None if row is None else row[0]


def ensure_can_create_password(cur, matricula: str) -> None:
    """Levanta StudentNotEligible se a matrícula não existir ou estiver inativa em pgl_proxy."""
    status = get_proxy_active_status(cur, matricula)
    if status is None:
        raise StudentNotEligible(f"Matrícula {matricula} não encontrada em pgl_proxy.students.")
    if not status:
        raise StudentNotEligible(f"Matrícula {matricula} está inativa em pgl_proxy.students.")


def hash_password(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def upsert_auth_record(cur, matricula: str, password_hash: str, is_active: bool) -> None:
    """Insere o registro de auth ou sobrescreve o existente para a mesma matrícula."""
    cur.execute(UPSERT_SQL, (matricula, password_hash, is_active))


def main() -> None:
    parser = argparse.ArgumentParser(description="Cria/atualiza um aluno no pgl_auth.")
    parser.add_argument("matricula")
    parser.add_argument("--inactive", action="store_true", help="Cria o aluno já como inativo")
    args = parser.parse_args()

    database_url = os.environ["NEON_DATABASE_URL"]

    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            try:
                ensure_can_create_password(cur, args.matricula)
            except StudentNotEligible as exc:
                raise SystemExit(str(exc)) from exc

        senha = getpass.getpass("Senha: ")
        confirmacao = getpass.getpass("Confirme a senha: ")
        if senha != confirmacao:
            raise SystemExit("As senhas não conferem.")

        password_hash = hash_password(senha)

        with conn.cursor() as cur:
            upsert_auth_record(cur, args.matricula, password_hash, not args.inactive)
        conn.commit()

    print(f"Aluno {args.matricula} salvo com sucesso.")


if __name__ == "__main__":
    main()
