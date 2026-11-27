from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from .client import PGLAuthClient


class AsyncPGLAuthClient:
    """Asynchronous wrapper around ``PGLAuthClient`` for asyncio programs.

    Every method runs the synchronous client in a worker thread, so the event
    loop is not blocked during HTTP calls. The methods take the same
    arguments and raise the same exceptions as the synchronous client.

    Parameters
    ----------
    **options : Any
        Keyword arguments passed to ``PGLAuthClient``.

    Example
    -------
    >>> async def main():  # doctest: +SKIP
    ...     client = AsyncPGLAuthClient()
    ...     token = await client.login("20231001", "Minha@Senha2026")
    """

    def __init__(self, **options: Any) -> None:
        """Create the synchronous client that does the work.

        Parameters
        ----------
        **options : Any
            Keyword arguments passed to ``PGLAuthClient``.

        Returns
        -------
        None
        """
        self._client = PGLAuthClient(**options)

    @property
    def token(self) -> Optional[str]:
        """Access token of the current session, or None.

        Returns
        -------
        str | None
            Token of the current session.
        """
        return self._client.token

    async def register(
        self,
        registration_number: str,
        email: str,
        password: str,
        password_confirmation: str,
    ) -> None:
        """Register a password. See ``PGLAuthClient.register``.

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

        Returns
        -------
        None
        """
        await asyncio.to_thread(
            self._client.register,
            registration_number,
            email,
            password,
            password_confirmation,
        )

    async def login(self, registration_number: str, password: str) -> str:
        """Log in and return the token. See ``PGLAuthClient.login``.

        Parameters
        ----------
        registration_number : str
            Registration number of the account.
        password : str
            Password of the account.

        Returns
        -------
        str
            Access token.
        """
        return await asyncio.to_thread(self._client.login, registration_number, password)

    async def restore_session(self, registration_number: str) -> bool:
        """Restore a cached session. See ``PGLAuthClient.restore_session``.

        Parameters
        ----------
        registration_number : str
            Account the cached token must belong to.

        Returns
        -------
        bool
            True when a valid cached token was loaded.
        """
        return await asyncio.to_thread(self._client.restore_session, registration_number)

    async def logout(self) -> None:
        """Revoke the current session. See ``PGLAuthClient.logout``.

        Returns
        -------
        None
        """
        await asyncio.to_thread(self._client.logout)

    async def change_password(self, current_password: str, new_password: str) -> None:
        """Change the password. See ``PGLAuthClient.change_password``.

        Parameters
        ----------
        current_password : str
            Password the account has now.
        new_password : str
            Password the account will have.

        Returns
        -------
        None
        """
        await asyncio.to_thread(self._client.change_password, current_password, new_password)

    async def request_password_reset(self, registration_number: str) -> None:
        """Send a reset code. See ``PGLAuthClient.request_password_reset``.

        Parameters
        ----------
        registration_number : str
            Registration number of the student.

        Returns
        -------
        None
        """
        await asyncio.to_thread(self._client.request_password_reset, registration_number)

    async def reset_password_with_code(
        self,
        registration_number: str,
        code: str,
        new_password: str,
    ) -> None:
        """Reset the password with a code. See the synchronous client.

        Parameters
        ----------
        registration_number : str
            Registration number of the student.
        code : str
            Code received by e-mail.
        new_password : str
            Password the account will have.

        Returns
        -------
        None
        """
        await asyncio.to_thread(
            self._client.reset_password_with_code,
            registration_number,
            code,
            new_password,
        )

    async def list_students(self) -> List[Dict[str, Any]]:
        """List the roster. See ``PGLAuthClient.list_students``.

        Returns
        -------
        list[dict]
            One dictionary per roster member.
        """
        return await asyncio.to_thread(self._client.list_students)

    async def set_student_status(self, registration_number: str, is_active: bool) -> None:
        """Block or unblock a student. See ``PGLAuthClient.set_student_status``.

        Parameters
        ----------
        registration_number : str
            Student whose account is changed.
        is_active : bool
            New status of the account.

        Returns
        -------
        None
        """
        await asyncio.to_thread(
            self._client.set_student_status, registration_number, is_active
        )

    async def send_invitations(self, registration_numbers: List[str]) -> Dict[str, Any]:
        """Invite students without a password. See the synchronous client.

        Parameters
        ----------
        registration_numbers : list[str]
            Students to invite, up to 200 per call.

        Returns
        -------
        dict
            Lists of ``sent`` and ``skipped`` students.
        """
        return await asyncio.to_thread(self._client.send_invitations, registration_numbers)

    async def reset_student_password(self, registration_number: str, new_password: str) -> None:
        """Set a student password as a professor. See the synchronous client.

        Parameters
        ----------
        registration_number : str
            Student whose password is set.
        new_password : str
            Password the student will have.

        Returns
        -------
        None
        """
        await asyncio.to_thread(
            self._client.reset_student_password, registration_number, new_password
        )
