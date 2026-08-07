"""Aplica db/schema.sql no banco apontado por NEON_DATABASE_URL (lido do .env)."""
from __future__ import annotations

import pathlib

import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

SCHEMA_PATH = pathlib.Path(__file__).parent / "schema.sql"


def main() -> None:
    database_url = os.environ["NEON_DATABASE_URL"]
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(schema_sql)
        conn.commit()

    print("Schema pgl_auth e tabela students aplicados com sucesso.")


if __name__ == "__main__":
    main()
