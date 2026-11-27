from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

DEFAULT_CACHE_PATH = Path.home() / ".pgl_auth" / "token.json"
EXPIRY_MARGIN_SECONDS = 60


class TokenCache:
    """Store the access token on disk so the student stays logged in.

    The file is written with permissions 600 on systems that support them.
    A token is never returned after it has expired, with a safety margin of
    one minute.

    Parameters
    ----------
    path : pathlib.Path | None
        File used to store the token. Defaults to ``~/.pgl_auth/token.json``.

    Example
    -------
    >>> cache = TokenCache()  # doctest: +SKIP
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        """Choose the file used to store the token.

        Parameters
        ----------
        path : pathlib.Path | None
            File used to store the token.

        Returns
        -------
        None
        """
        self.path = Path(path) if path is not None else DEFAULT_CACHE_PATH

    def save(
        self,
        registration_number: str,
        access_token: str,
        expires_in: int,
    ) -> None:
        """Write the token and its expiration time to the cache file.

        Parameters
        ----------
        registration_number : str
            Account the token belongs to.
        access_token : str
            Token to store.
        expires_in : int
            Lifetime of the token in seconds, counted from now.

        Returns
        -------
        None
        """
        payload = {
            "registration_number": registration_number,
            "access_token": access_token,
            "expires_at": time.time() + expires_in,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)

    def load(self, registration_number: str) -> Optional[str]:
        """Read the cached token of an account, if it is still valid.

        Parameters
        ----------
        registration_number : str
            Account whose token is wanted.

        Returns
        -------
        str | None
            Token, or None when the file is missing, unreadable, belongs to
            another account or is about to expire.
        """
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if payload.get("registration_number") != registration_number:
            return None
        if float(payload.get("expires_at", 0)) - EXPIRY_MARGIN_SECONDS <= time.time():
            return None
        return payload.get("access_token")

    def clear(self) -> None:
        """Delete the cache file if it exists.

        Returns
        -------
        None
        """
        self.path.unlink(missing_ok=True)
