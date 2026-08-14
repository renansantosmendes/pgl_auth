-- Schema e tabela de autenticação dos alunos para o pgl_auth.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS pgl_auth;

CREATE TABLE IF NOT EXISTS pgl_auth.students (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    registration_number TEXT NOT NULL UNIQUE,
    password_hash     TEXT NOT NULL,
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One-time migration for environments created before the matricula ->
-- registration_number rename; no-op once already renamed.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'pgl_auth' AND table_name = 'students'
          AND column_name = 'matricula'
    ) THEN
        ALTER TABLE pgl_auth.students RENAME COLUMN matricula TO registration_number;
    END IF;
END $$;

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
