class PGLAuthError(Exception):
    """Erro base para falhas de autenticação no pgl_auth."""


class AuthenticationError(PGLAuthError):
    """Matrícula ou senha inválidos."""


class InactiveAccountError(PGLAuthError):
    """Conta do aluno está inativa."""
