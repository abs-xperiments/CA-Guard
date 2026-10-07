"""Signed session cookies.

A session is a signed statement of "this is user X, until time T". Nothing is
stored server-side, so there is no session table to grow or clean up, and
signing means the cookie cannot be edited by whoever holds it.

The signing key is generated on first run and kept in the data directory beside
the review database. That means no founder has to invent a secret, nothing has
to be configured to get started, and sessions survive a restart — but an
operator who wants to rotate the key can simply delete the file, which logs
everyone out.
"""

from __future__ import annotations

import base64
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

#: A working day plus a margin. Long enough that a reviewer is not logged out
#: mid-engagement; short enough that a forgotten open laptop expires overnight.
SESSION_SECONDS = 12 * 60 * 60

COOKIE_NAME = "caguard_session"
KEY_FILENAME = "session.key"
MIN_KEY_BYTES = 32


class InvalidSessionError(ValueError):
    """The cookie is missing, tampered with, or expired."""


@dataclass(frozen=True)
class SessionToken:
    user_id: str
    email: str
    expires_at: float
    #: The user's session epoch when this was issued. Signing out bumps the
    #: epoch, which ends every session issued before — including copies.
    epoch: int = 0

    @property
    def expired(self) -> bool:
        return time.time() >= self.expires_at


def load_or_create_key(directory: Path) -> bytes:
    """The signing key, generated once and kept beside the database.

    Written with owner-only permissions. If it is lost or deleted, every session
    becomes invalid, which is the correct behaviour for a lost signing key.
    """
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / KEY_FILENAME
    if path.exists():
        key = path.read_bytes()
        if len(key) < MIN_KEY_BYTES:
            # An empty or truncated key would let anyone forge a session.
            raise RuntimeError(
                f"{path} holds a {len(key)}-byte signing key; at least {MIN_KEY_BYTES} are "
                "needed. Delete the file to generate a new one (everyone will be signed out)."
            )
        return key

    key = secrets.token_bytes(32)
    # Created owner-only from the first byte, not chmodded after writing.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(key)
    return key


def issue(
    key: bytes, user_id: str, email: str, *, epoch: int = 0, seconds: int = SESSION_SECONDS
) -> str:
    """Create a signed session cookie value."""
    payload = {
        "sub": user_id,
        "email": email,
        "ep": epoch,
        "exp": time.time() + seconds,
        # A nonce, so two cookies issued in the same second differ.
        "jti": secrets.token_hex(8),
    }
    body = _b64(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    return f"{body}.{_b64(_sign(key, body))}"


def read(key: bytes, cookie: str | None) -> SessionToken:
    """Validate a cookie and return who it says the user is.

    Raises rather than returning ``None``, because every failure here — missing,
    tampered, expired — should end the request the same way, and a caller that
    forgets to check a return value should not silently get an anonymous user.
    """
    if not cookie:
        raise InvalidSessionError("no session cookie")

    try:
        body, signature = cookie.split(".", 1)
    except ValueError as exc:
        raise InvalidSessionError("malformed session cookie") from exc

    if not hmac.compare_digest(_sign(key, body), _unb64(signature)):
        raise InvalidSessionError("session signature does not match")

    try:
        payload = json.loads(_unb64(body))
        token = SessionToken(
            user_id=str(payload["sub"]),
            email=str(payload["email"]),
            expires_at=float(payload["exp"]),
            # Absent on cookies issued before epochs existed: those read as 0,
            # which every account starts at, so the upgrade logs nobody out.
            epoch=int(payload.get("ep", 0)),
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise InvalidSessionError("unreadable session cookie") from exc

    if token.expired:
        raise InvalidSessionError("session expired")
    return token


def _sign(key: bytes, body: str) -> bytes:
    return hmac.new(key, body.encode(), sha256).digest()


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)
