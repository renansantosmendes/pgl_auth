"""Garante as regras de negócio de db/create_student.py:

1. Só é possível criar/atualizar senha se a matrícula existir e estiver
   ativa em pgl_proxy.students.
2. Um registro existente em pgl_auth.students é sobrescrito (upsert), não
   duplicado, quando o mesmo aluno é recriado.
"""
from __future__ import annotations

import bcrypt
import pytest

from db.create_student import (
    UPSERT_SQL,
    StudentNotEligible,
    ensure_can_create_password,
    get_proxy_active_status,
    hash_password,
    upsert_auth_record,
)


class FakeCursor:
    """Cursor falso que responde com uma fila de resultados pré-definida."""

    def __init__(self, fetchone_result=None):
        self._fetchone_result = fetchone_result
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchone(self):
        return self._fetchone_result


# --- Regra 1: elegibilidade via pgl_proxy.students ---------------------------------


def test_get_proxy_active_status_returns_true_when_active():
    cur = FakeCursor(fetchone_result=(True,))
    assert get_proxy_active_status(cur, "202100001") is True


def test_get_proxy_active_status_returns_false_when_inactive():
    cur = FakeCursor(fetchone_result=(False,))
    assert get_proxy_active_status(cur, "202100001") is False


def test_get_proxy_active_status_returns_none_when_not_found():
    cur = FakeCursor(fetchone_result=None)
    assert get_proxy_active_status(cur, "inexistente") is None


def test_ensure_can_create_password_allows_active_student():
    cur = FakeCursor(fetchone_result=(True,))
    ensure_can_create_password(cur, "202100001")  # não deve levantar


def test_ensure_can_create_password_blocks_missing_student():
    cur = FakeCursor(fetchone_result=None)
    with pytest.raises(StudentNotEligible, match="não encontrada"):
        ensure_can_create_password(cur, "inexistente")


def test_ensure_can_create_password_blocks_inactive_student():
    cur = FakeCursor(fetchone_result=(False,))
    with pytest.raises(StudentNotEligible, match="inativa"):
        ensure_can_create_password(cur, "202100001")


# --- Regra 2: upsert sobrescreve registro existente em pgl_auth --------------------


def test_upsert_auth_record_uses_on_conflict_do_update():
    """A query precisa ser um upsert (ON CONFLICT DO UPDATE), não um INSERT simples,
    para garantir que recriar um aluno já cadastrado sobrescreve o registro em vez
    de falhar por violação de unicidade ou criar um duplicado."""
    assert "ON CONFLICT" in UPSERT_SQL
    assert "DO UPDATE" in UPSERT_SQL
    assert "password_hash = EXCLUDED.password_hash" in UPSERT_SQL
    assert "is_active = EXCLUDED.is_active" in UPSERT_SQL


def test_upsert_auth_record_sends_expected_params():
    cur = FakeCursor()
    upsert_auth_record(cur, "202100001", "hash-fake", True)
    assert cur.executed == [(UPSERT_SQL, ("202100001", "hash-fake", True))]


# --- hashing -------------------------------------------------------------------


def test_hash_password_is_not_plaintext_and_verifies_with_bcrypt():
    hashed = hash_password("minha_senha")
    assert hashed != "minha_senha"
    assert bcrypt.checkpw(b"minha_senha", hashed.encode("utf-8"))
    assert not bcrypt.checkpw(b"senha_errada", hashed.encode("utf-8"))
