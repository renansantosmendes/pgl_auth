-- Schema e tabela de autenticação dos alunos para o pgl_auth.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS pgl_auth;

CREATE TABLE IF NOT EXISTS pgl_auth.students (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    matricula     TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION pgl_auth.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_students_updated_at ON pgl_auth.students;

CREATE TRIGGER trg_students_updated_at
    BEFORE UPDATE ON pgl_auth.students
    FOR EACH ROW
    EXECUTE FUNCTION pgl_auth.set_updated_at();
