from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

import requests

from . import validation
from .exceptions import (
    AlreadyRegisteredError,
    AuthenticationError,
    InactiveAccountError,
    InvalidInputError,
    InvalidResetCodeError,
    PermissionDeniedError,
    PGLAuthError,
    RateLimitedError,
    SessionExpiredError,
)
from .token_cache import TokenCache

DEFAULT_BASE_URL = "https://pgl-auth-server.vercel.app"
BASE_URL_ENV_VAR = "PGL_AUTH_BASE_URL"
API_URL_ENV_VAR = "PGL_AUTH_API_URL"
REGISTER_URL_ENV_VAR = "PGL_AUTH_REGISTER_URL"
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 0.5
RETRY_STATUS_CODES = (502, 503, 504)
CONNECTION_ERROR_MESSAGE = "Falha ao contatar o serviço de autenticação"
WRONG_CURRENT_PASSWORD = "Senha atual inválida."


class PGLAuthClient:
    """Client for the pgl_auth API used by students and professors.

    Parameters
    ----------
    api_url : str | None
        Full URL of the login endpoint. Defaults to ``<base_url>/api/login``.
    register_url : str | None
        Full URL of the registration endpoint. Defaults to
        ``<base_url>/api/register``.
    timeout : float
        Timeout of each HTTP request, in seconds.
    base_url : str | None
        Base URL of the API. Defaults to the ``PGL_AUTH_BASE_URL`` variable,
        then to the public deployment.
    token_cache : TokenCache | None
        Where the token is saved after login, so it can be restored later.

    Example
    -------
    >>> client = PGLAuthClient()  # doctest: +SKIP
    >>> client.login("20231001", "Minha@Senha2026")  # doctest: +SKIP
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        register_url: Optional[str] = None,
        timeout: float = 10.0,
        base_url: Optional[str] = None,
        token_cache: Optional[TokenCache] = None,
    ) -> None:
        resolved_base = base_url or os.environ.get(BASE_URL_ENV_VAR, DEFAULT_BASE_URL)
        self.base_url = resolved_base.rstrip("/")
        self.api_url = api_url or os.environ.get(
            API_URL_ENV_VAR, f"{self.base_url}/api/login"
        )
        self.register_url = register_url or os.environ.get(
            REGISTER_URL_ENV_VAR, f"{self.base_url}/api/register"
        )
        self.timeout = timeout
        self._token_cache = token_cache
        self._token: Optional[str] = None
        self._registration_number: Optional[str] = None

    @property
    def token(self) -> Optional[str]:
        """Access token of the current session, or None.

        Returns
        -------
        str | None
            Token issued by the last successful login or password change.
        """
        return self._token

    def auth_header(self) -> Dict[str, str]:
        """Build the Authorization header for the model proxy.

        Returns
        -------
        dict[str, str]
            Header with the bearer token.

        Raises
        ------
        PGLAuthError
            If there is no session. Call ``login()`` first.
        """
        if not self._token:
            raise PGLAuthError("Nenhum token disponível. Chame login() primeiro.")
        return {"Authorization": f"Bearer {self._token}"}

    def register(
        self,
        registration_number: str,
        email: str,
        password: str,
        password_confirmation: str,
    ) -> None:
        """Create the password of an enrolled student for the first time.

        All four values are mandatory. The e-mail must be the institutional
        address registered on the course roster. The password must follow
        the strength rules, which are checked here before the request.

        Parameters
        ----------
        registration_number : str
            Registration number with 5 to 20 digits.
        email : str
            Institutional e-mail address of the student.
        password : str
            New password.
        password_confirmation : str
            The same password typed again.

        Raises
        ------
        InvalidInputError
            If a value breaks the format or the password rules.
        InactiveAccountError
            If the student is not enrolled, or the e-mail does not match.
        AlreadyRegisteredError
            If the registration number already has a password.
        """
        problems = validation.registration_number_problems(registration_number)
        problems += validation.email_problems(email)
        if password != password_confirmation:
            problems.append("As senhas não coincidem.")
        problems += validation.password_problems(password, registration_number)
        if problems:
            raise InvalidInputError(problems)

        response = self._request(
            "POST",
            self.register_url,
            {
                "registration_number": registration_number,
                "email": email,
                "senha": password,
                "senha_confirmacao": password_confirmation,
            },
        )
        if response.status_code == 201:
            return
        if response.status_code == 403:
            raise InactiveAccountError(self._detail(response, "Cadastro não permitido."))
        if response.status_code == 409:
            raise AlreadyRegisteredError("Essa matrícula já possui uma senha cadastrada.")
        self._raise_for_common_errors(response, "Erro ao cadastrar")

    def login(self, registration_number: str, password: str) -> str:
        """Check the password and return the access token (valid 4 hours).

        The token is also saved in the token cache, when one is configured.

        Parameters
        ----------
        registration_number : str
            Registration number of the student or professor.
        password : str
            Password of the account.

        Returns
        -------
        str
            Access token.

        Raises
        ------
        AuthenticationError
            If the registration number or the password is wrong.
        InactiveAccountError
            If the account is blocked.
        RateLimitedError
            If the account is locked after too many wrong attempts.
        """
        response = self._request(
            "POST",
            self.api_url,
            {"registration_number": registration_number, "senha": password},
        )
        if response.status_code == 401:
            raise AuthenticationError(
                self._detail(response, "Matrícula ou senha inválidos.")
            )
        if response.status_code == 403:
            raise InactiveAccountError(self._detail(response, "Cadastro do aluno está inativo."))
        if response.status_code == 429:
            raise RateLimitedError(self._detail(response, "Conta bloqueada temporariamente."))
        self._raise_for_common_errors(response, "Erro ao autenticar")

        data = response.json()
        self._store_session(registration_number, data["access_token"], data.get("expires_in", 14400))
        return self._token

    def restore_session(self, registration_number: str) -> bool:
        """Load a token saved earlier in the token cache.

        Parameters
        ----------
        registration_number : str
            Account the saved token must belong to.

        Returns
        -------
        bool
            True when a valid saved token was loaded.
        """
        if self._token_cache is None:
            return False
        token = self._token_cache.load(registration_number)
        if token is None:
            return False
        self._token = token
        self._registration_number = registration_number
        return True

    def logout(self) -> None:
        """Revoke every token of the current account and forget the local one.

        Raises
        ------
        SessionExpiredError
            If there is no session, or the token was already revoked.
        """
        headers = self._auth_headers()
        response = self._request("POST", self._url("/api/logout"), headers=headers)
        self._forget_session()
        if response.status_code == 401:
            raise SessionExpiredError(self._detail(response, "Sessão inválida."))
        self._raise_for_common_errors(response, "Erro ao encerrar a sessão")

    def change_password(self, current_password: str, new_password: str) -> None:
        """Replace the password of the logged in account.

        A new token is returned by the server and replaces the current one,
        so the session stays open. Older tokens stop working.

        Parameters
        ----------
        current_password : str
            Password the account has now.
        new_password : str
            Password the account will have.

        Raises
        ------
        InvalidInputError
            If the new password breaks the strength rules.
        AuthenticationError
            If the current password is wrong.
        SessionExpiredError
            If there is no session or the token was revoked.
        RateLimitedError
            If the account is locked after too many wrong attempts.
        """
        headers = self._auth_headers()
        problems = validation.password_problems(
            new_password, self._registration_number or ""
        )
        if problems:
            raise InvalidInputError(problems)

        response = self._request(
            "POST",
            self._url("/api/password/change"),
            {"senha_atual": current_password, "nova_senha": new_password},
            headers=headers,
        )
        if response.status_code == 200:
            data = response.json()
            self._store_session(
                self._registration_number or "",
                data["access_token"],
                data.get("expires_in", 14400),
            )
            return
        if response.status_code == 401:
            detail = self._detail(response, "Sessão inválida.")
            if detail == WRONG_CURRENT_PASSWORD:
                raise AuthenticationError(detail)
            raise SessionExpiredError(detail)
        if response.status_code == 429:
            raise RateLimitedError(self._detail(response, "Conta bloqueada temporariamente."))
        self._raise_for_common_errors(response, "Erro ao trocar a senha")

    def request_password_reset(self, registration_number: str) -> None:
        """Ask the server to e-mail a reset code to the student.

        The server answers the same way whether or not a code was sent, so
        this method does not report whether the registration number exists.

        Parameters
        ----------
        registration_number : str
            Registration number of the student.

        Raises
        ------
        InvalidInputError
            If the registration number has an invalid format.
        """
        problems = validation.registration_number_problems(registration_number)
        if problems:
            raise InvalidInputError(problems)
        response = self._request(
            "POST",
            self._url("/api/password/forgot"),
            {"registration_number": registration_number},
        )
        if response.status_code == 202:
            return
        self._raise_for_common_errors(response, "Erro ao pedir o código")

    def reset_password_with_code(
        self,
        registration_number: str,
        code: str,
        new_password: str,
    ) -> None:
        """Set a new password using the code received by e-mail.

        Parameters
        ----------
        registration_number : str
            Registration number of the student.
        code : str
            Code received by e-mail.
        new_password : str
            Password the account will have.

        Raises
        ------
        InvalidInputError
            If the new password breaks the strength rules.
        InvalidResetCodeError
            If the code is wrong, expired, or was used too many times.
        """
        problems = validation.password_problems(new_password, registration_number)
        if problems:
            raise InvalidInputError(problems)
        response = self._request(
            "POST",
            self._url("/api/password/reset"),
            {
                "registration_number": registration_number,
                "codigo": code,
                "nova_senha": new_password,
            },
        )
        if response.status_code == 200:
            return
        if response.status_code == 400:
            raise InvalidResetCodeError(self._detail(response, "Código inválido ou expirado."))
        self._raise_for_common_errors(response, "Erro ao redefinir a senha")

    def list_students(self) -> List[Dict[str, Any]]:
        """List the roster with the state of each password account.

        Returns
        -------
        list[dict]
            One dictionary per roster member, with the keys
            ``registration_number``, ``full_name``, ``login_id``,
            ``roster_active``, ``has_password`` and ``account_active``.

        Raises
        ------
        PermissionDeniedError
            If the caller is not a professor.
        """
        headers = self._auth_headers()
        response = self._request("GET", self._url("/api/professor/students"), headers=headers)
        self._raise_for_professor_errors(response)
        return response.json()["students"]

    def set_student_status(self, registration_number: str, is_active: bool) -> None:
        """Block or unblock the password login of a student.

        Parameters
        ----------
        registration_number : str
            Student whose account is changed.
        is_active : bool
            New status of the account.

        Raises
        ------
        PermissionDeniedError
            If the caller is not a professor.
        PGLAuthError
            If the student has no password account yet.
        """
        headers = self._auth_headers()
        response = self._request(
            "POST",
            self._url(f"/api/professor/students/{registration_number}/status"),
            {"is_active": is_active},
            headers=headers,
        )
        if response.status_code == 404:
            raise PGLAuthError(self._detail(response, "Aluno sem senha cadastrada."))
        self._raise_for_professor_errors(response)

    def send_invitations(self, registration_numbers: List[str]) -> Dict[str, Any]:
        """Send password creation codes to enrolled students without a password.

        Parameters
        ----------
        registration_numbers : list[str]
            Students to invite, up to 200 per call.

        Returns
        -------
        dict
            ``sent``: registration numbers that received an invitation.
            ``skipped``: entries with ``registration_number`` and ``reason``.

        Raises
        ------
        PermissionDeniedError
            If the caller is not a professor.
        InvalidInputError
            If the list is empty or has more than 200 items.
        """
        headers = self._auth_headers()
        response = self._request(
            "POST",
            self._url("/api/professor/invitations"),
            {"registration_numbers": list(registration_numbers)},
            headers=headers,
        )
        if response.status_code == 422:
            raise InvalidInputError(self._problems(response))
        self._raise_for_professor_errors(response)
        return response.json()

    def reset_student_password(self, registration_number: str, new_password: str) -> None:
        """Set the password of a student on the student's behalf.

        Parameters
        ----------
        registration_number : str
            Student whose password is set.
        new_password : str
            Password the student will have.

        Raises
        ------
        InvalidInputError
            If the password breaks the strength rules.
        PermissionDeniedError
            If the caller is not a professor.
        """
        headers = self._auth_headers()
        problems = validation.password_problems(new_password, registration_number)
        if problems:
            raise InvalidInputError(problems)
        response = self._request(
            "POST",
            self._url("/api/reset-password"),
            {"registration_number": registration_number, "new_senha": new_password},
            headers=headers,
        )
        if response.status_code == 422:
            raise InvalidInputError(self._problems(response))
        self._raise_for_professor_errors(response)

    def _url(self, path: str) -> str:
        """Join the base URL with an endpoint path.

        Parameters
        ----------
        path : str
            Path that starts with a slash.

        Returns
        -------
        str
            Full URL of the endpoint.
        """
        return f"{self.base_url}{path}"

    def _auth_headers(self) -> Dict[str, str]:
        """Return the bearer header, or fail when there is no session.

        Returns
        -------
        dict[str, str]
            Authorization header of the current session.

        Raises
        ------
        SessionExpiredError
            If there is no session.
        """
        if not self._token:
            raise SessionExpiredError("Faça login antes de usar esta operação.")
        return {"Authorization": f"Bearer {self._token}"}

    def _store_session(
        self,
        registration_number: str,
        token: str,
        expires_in: int,
    ) -> None:
        """Keep the new token in memory and, when configured, in the cache.

        Parameters
        ----------
        registration_number : str
            Account the token belongs to.
        token : str
            Access token returned by the server.
        expires_in : int
            Lifetime of the token in seconds.

        Returns
        -------
        None
        """
        self._token = token
        self._registration_number = registration_number or None
        if self._token_cache is not None and registration_number:
            self._token_cache.save(registration_number, token, expires_in)

    def _forget_session(self) -> None:
        """Drop the token from memory and from the cache.

        Returns
        -------
        None
        """
        self._token = None
        self._registration_number = None
        if self._token_cache is not None:
            self._token_cache.clear()

    def _request(
        self,
        method: str,
        url: str,
        payload: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> requests.Response:
        """Send a request, retrying connection errors and gateway errors.

        Parameters
        ----------
        method : str
            ``GET`` or ``POST``.
        url : str
            Full URL of the endpoint.
        payload : dict | None
            JSON body of the request.
        headers : dict | None
            Extra headers, for example the bearer token.

        Returns
        -------
        requests.Response
            Last response received.

        Raises
        ------
        PGLAuthError
            If every attempt failed to reach the server.
        """
        send = requests.get if method == "GET" else requests.post
        for attempt in range(1, MAX_ATTEMPTS + 1):
            kwargs: Dict[str, Any] = {"timeout": self.timeout}
            if payload is not None:
                kwargs["json"] = payload
            if headers:
                kwargs["headers"] = headers
            try:
                response = send(url, **kwargs)
            except requests.RequestException as exc:
                if attempt == MAX_ATTEMPTS:
                    raise PGLAuthError(f"{CONNECTION_ERROR_MESSAGE}: {exc}") from exc
                time.sleep(BACKOFF_SECONDS * 2 ** (attempt - 1))
                continue
            if response.status_code in RETRY_STATUS_CODES and attempt < MAX_ATTEMPTS:
                time.sleep(BACKOFF_SECONDS * 2 ** (attempt - 1))
                continue
            return response
        raise PGLAuthError(CONNECTION_ERROR_MESSAGE)

    def _raise_for_professor_errors(self, response: requests.Response) -> None:
        """Map the status codes shared by the professor endpoints.

        Parameters
        ----------
        response : requests.Response
            Response to check.

        Raises
        ------
        SessionExpiredError
            For status 401.
        PermissionDeniedError
            For status 403.
        PGLAuthError
            For any other error status.
        """
        if response.status_code < 400:
            return
        if response.status_code == 401:
            raise SessionExpiredError(self._detail(response, "Sessão inválida."))
        if response.status_code == 403:
            raise PermissionDeniedError(self._detail(response, "Ação restrita a professores."))
        self._raise_for_common_errors(response, "Erro na operação")

    def _raise_for_common_errors(
        self,
        response: requests.Response,
        context: str,
    ) -> None:
        """Map the status codes shared by most endpoints.

        Parameters
        ----------
        response : requests.Response
            Response to check.
        context : str
            Prefix of the message used for unexpected errors.

        Raises
        ------
        InvalidInputError
            For status 422, with the problems reported by the server.
        PGLAuthError
            For any other error status.
        """
        if response.status_code == 422:
            raise InvalidInputError(self._problems(response))
        if response.status_code >= 400:
            raise PGLAuthError(f"{context}: {self._detail(response, str(response.status_code))}")

    @staticmethod
    def _detail(response: requests.Response, default: str) -> str:
        """Read the human readable message of an error response.

        Parameters
        ----------
        response : requests.Response
            Response that may carry a ``detail`` field.
        default : str
            Text used when the response has no readable message.

        Returns
        -------
        str
            Message sent by the server, or ``default``.
        """
        try:
            body = response.json()
        except ValueError:
            return default
        detail = body.get("detail") if isinstance(body, dict) else None
        if isinstance(detail, dict):
            return detail.get("message", default)
        if isinstance(detail, str):
            return detail
        return default

    @staticmethod
    def _problems(response: requests.Response) -> List[str]:
        """Read the list of rules reported by a 422 response.

        Parameters
        ----------
        response : requests.Response
            Response of the server.

        Returns
        -------
        list[str]
            Problems listed by the server, or a generic message.
        """
        try:
            detail = response.json().get("detail", {})
        except (ValueError, AttributeError):
            detail = {}
        errors = detail.get("errors") if isinstance(detail, dict) else None
        return list(errors) if errors else ["Dados inválidos."]


def register(
    registration_number: str,
    email: str,
    password: str,
    password_confirmation: str,
    register_url: Optional[str] = None,
) -> None:
    """Shortcut to register a password without creating a client first.

    Parameters
    ----------
    registration_number : str
        Registration number of the student.
    email : str
        Institutional e-mail address of the student.
    password : str
        New password.
    password_confirmation : str
        The same password typed again.
    register_url : str | None
        Optional registration endpoint.

    Returns
    -------
    None
    """
    PGLAuthClient(register_url=register_url).register(
        registration_number, email, password, password_confirmation
    )


def login(
    registration_number: str,
    password: str,
    api_url: Optional[str] = None,
) -> str:
    """Shortcut to log in without creating a client first.

    Parameters
    ----------
    registration_number : str
        Registration number of the student.
    password : str
        Password of the account.
    api_url : str | None
        Optional login endpoint.

    Returns
    -------
    str
        Access token.
    """
    return PGLAuthClient(api_url=api_url).login(registration_number, password)
