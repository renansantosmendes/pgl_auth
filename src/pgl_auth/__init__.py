from importlib.metadata import PackageNotFoundError, version

from .async_client import AsyncPGLAuthClient
from .client import PGLAuthClient, login, register
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

__all__ = [
    "AsyncPGLAuthClient",
    "PGLAuthClient",
    "TokenCache",
    "login",
    "register",
    "PGLAuthError",
    "AuthenticationError",
    "InactiveAccountError",
    "AlreadyRegisteredError",
    "InvalidInputError",
    "InvalidResetCodeError",
    "PermissionDeniedError",
    "RateLimitedError",
    "SessionExpiredError",
]

try:
    __version__ = version("pgl-auth")
except PackageNotFoundError:
    __version__ = "0.0.0"
