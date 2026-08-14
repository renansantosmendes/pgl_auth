from importlib.metadata import PackageNotFoundError, version

from .client import PGLAuthClient, login, register
from .exceptions import (
    AlreadyRegisteredError,
    AuthenticationError,
    InactiveAccountError,
    PGLAuthError,
)

__all__ = [
    "PGLAuthClient",
    "login",
    "register",
    "PGLAuthError",
    "AuthenticationError",
    "InactiveAccountError",
    "AlreadyRegisteredError",
]

try:
    __version__ = version("pgl-auth")
except PackageNotFoundError:
    __version__ = "0.0.0"
