from importlib.metadata import PackageNotFoundError, version

from .client import PGLAuthClient, login
from .exceptions import PGLAuthError, AuthenticationError, InactiveAccountError

__all__ = [
    "PGLAuthClient",
    "login",
    "PGLAuthError",
    "AuthenticationError",
    "InactiveAccountError",
]

try:
    __version__ = version("pgl-auth")
except PackageNotFoundError:
    __version__ = "0.0.0"
