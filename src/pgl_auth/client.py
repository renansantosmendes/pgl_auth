from __future__ import annotations

import os

import requests

from .exceptions import (
    AlreadyRegisteredError,
    AuthenticationError,
    InactiveAccountError,
    PGLAuthError,
)

DEFAULT_API_URL = "https://pgl-auth-server.vercel.app/api/login"
DEFAULT_REGISTER_URL = "https://pgl-auth-server.vercel.app/api/register"
API_URL_ENV_VAR = "PGL_AUTH_API_URL"
REGISTER_URL_ENV_VAR = "PGL_AUTH_REGISTER_URL"


class PGLAuthClient:
    """Cliente para autenticar alunos e obter o token de acesso ao proxy de modelos."""

    def __init__(
        self,
        api_url: str | None = None,
        register_url: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.api_url = api_url or os.environ.get(API_URL_ENV_VAR, DEFAULT_API_URL)
        self.register_url = register_url or os.environ.get(
            REGISTER_URL_ENV_VAR, DEFAULT_REGISTER_URL
        )
        self.timeout = timeout
        self._token: str | None = None

    def register(self, registration_number: str, password: str) -> None:
        """Cadastra a senha do aluno pela primeira vez.

        Só funciona uma vez por matrícula: se ela já tiver uma senha
        cadastrada, levanta `AlreadyRegisteredError` (não há reset
        self-service — matrícula sozinha não é segredo). Depois de
        registrar, chame `login()` para obter o token.
        """
        try:
            response = requests.post(
                self.register_url,
                json={"registration_number": registration_number, "senha": password},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise PGLAuthError(f"Falha ao contatar o serviço de autenticação: {exc}") from exc

        if response.status_code == 403:
            raise InactiveAccountError(
                "Matrícula não encontrada ou inativa na disciplina."
            )
        if response.status_code == 409:
            raise AlreadyRegisteredError("Essa matrícula já possui uma senha cadastrada.")

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise PGLAuthError(f"Erro ao cadastrar: {exc}") from exc

    def login(self, registration_number: str, password: str) -> str:
        """Autentica o aluno e retorna o token JWT (válido por 4 horas)."""
        try:
            response = requests.post(
                self.api_url,
                json={"registration_number": registration_number, "senha": password},
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


def register(registration_number: str, password: str, register_url: str | None = None) -> None:
    """Atalho para cadastrar a senha sem instanciar PGLAuthClient diretamente."""
    PGLAuthClient(register_url=register_url).register(registration_number, password)


def login(registration_number: str, password: str, api_url: str | None = None) -> str:
    """Atalho para autenticar sem instanciar PGLAuthClient diretamente."""
    return PGLAuthClient(api_url=api_url).login(registration_number, password)
