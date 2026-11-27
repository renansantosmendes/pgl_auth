from __future__ import annotations

from typing import List


class PGLAuthError(Exception):
    """Base error for every failure raised by pgl_auth.

    Catch this class to handle any problem reported by the client.
    """


class AuthenticationError(PGLAuthError):
    """Wrong registration number or password, or a wrong current password."""


class InactiveAccountError(PGLAuthError):
    """The account is inactive, or the student is not enrolled and active."""


class AlreadyRegisteredError(PGLAuthError):
    """The registration number already has a password."""


class InvalidInputError(PGLAuthError):
    """A value was rejected by the format or password rules.

    Attributes
    ----------
    problems : list[str]
        Human readable description of every rule that was broken.
    """

    def __init__(self, problems: List[str]) -> None:
        """Store the problems and build the message from them.

        Parameters
        ----------
        problems : list[str]
            Rules that the value broke.

        Returns
        -------
        None
        """
        self.problems = list(problems)
        super().__init__("; ".join(self.problems) or "Dados inválidos.")


class RateLimitedError(PGLAuthError):
    """Too many wrong attempts: the account is temporarily locked."""


class InvalidResetCodeError(PGLAuthError):
    """The reset code is wrong, expired, or was used too many times."""


class SessionExpiredError(PGLAuthError):
    """The token is missing, expired or was revoked. Log in again."""


class PermissionDeniedError(PGLAuthError):
    """The caller is authenticated but is not allowed to do this action."""
