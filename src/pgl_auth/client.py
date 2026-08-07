from __future__ import annotations

import os

import requests

from .exceptions import AuthenticationError, InactiveAccountError, PGLAuthError

DEFAULT_API_URL = "https://pgl-auth.vercel.app/api/login"
API_URL_ENV_VAR = "PGL_AUTH_API_URL"


class PGLAuthClient:
    """Cliente para autenticar alunos e obter o token de acesso ao proxy de modelos."""

    def __init__(self, api_url: str | None = None, timeout: float = 10.0) -> None:
        self.api_url = api_url or os.environ.get(API_URL_ENV_VAR, DEFAULT_API_URL)
        self.timeout = timeout
        self._token: str | None = None

    def login(self, matricula: str, senha: str) -> str:
        """Autentica o aluno e retorna o token JWT (válido por 4 horas)."""
        try:
            response = requests.post(
                self.api_url,
                json={"matricula": matricula, "senha": senha},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise PGLAuthError(f"Falha ao contatar o serviço de autenticação: {exc}") from exc

        if response.status_code == 401:
            raise AuthenticationError("Matrícula ou senha inválidos.")
        if response.status_code == 403:
            raise InactiveAccountError("Cadastro do aluno está inativo.")

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise PGLAuthError(f"Erro ao autenticar: {exc}") from exc

        data = response.json()
        self._token = data["access_token"]
        return self._token

    @property
    def token(self) -> str | None:
        return self._token

    def auth_header(self) -> dict[str, str]:
        """Retorna o cabeçalho Authorization pronto para chamar o proxy de modelos."""
        if not self._token:
            raise PGLAuthError("Nenhum token disponível. Chame login() primeiro.")
        return {"Authorization": f"Bearer {self._token}"}


def login(matricula: str, senha: str, api_url: str | None = None) -> str:
    """Atalho para autenticar sem instanciar PGLAuthClient diretamente."""
    return PGLAuthClient(api_url=api_url).login(matricula, senha)
