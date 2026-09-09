"""Password hashing.

Uses ``hashlib.scrypt`` from the standard library. It is a memory-hard function,
which is the property that matters — an attacker with a stolen database should
find guessing expensive in RAM as well as CPU, because RAM is what does not
parallelise cheaply on a GPU.

No dependency is added for this. Argon2 would be marginally preferable, but it
is a compiled package, and scrypt at these parameters is well within what a
review would accept for a self-hosted audit tool.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

#: scrypt cost parameters. n=2^14 with r=8 needs about 16 MB per hash, which is
#: unnoticeable when one person logs in and expensive when someone is guessing.
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SALT_BYTES = 16
KEY_BYTES = 32

#: Stored as ``scrypt$n$r$p$salt$hash``, so the parameters travel with the hash
#: and can be raised later without invalidating existing passwords.
PREFIX = "scrypt"

MIN_PASSWORD_LENGTH = 10


class WeakPasswordError(ValueError):
    """The password is too weak to accept. The message is shown to the user."""


def hash_password(password: str) -> str:
    """Hash a password for storage. Never store or log the password itself."""
    check_strength(password)
    salt = secrets.token_bytes(SALT_BYTES)
    derived = _derive(password, salt)
    return f"{PREFIX}${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Check a password against a stored hash, in constant time."""
    try:
        prefix, n, r, p, salt_hex, expected_hex = stored.split("$")
        if prefix != PREFIX:
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(expected_hex)
        derived = _derive(password, salt, n=int(n), r=int(r), p=int(p))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(derived, expected)


def check_strength(password: str) -> None:
    """Reject passwords that are trivially guessable.

    Length does more than character-class rules, which mostly teach people to
    write ``Password1!``. A long passphrase is both stronger and easier to
    remember, so length is what is required.
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPasswordError(
            f"Use at least {MIN_PASSWORD_LENGTH} characters. A short phrase you "
            "will remember is stronger than a short word with symbols in it."
        )
    if password.lower() in _COMMON:
        raise WeakPasswordError(
            "That is one of the most commonly used passwords. Please choose another."
        )
    if len(set(password)) < 5:
        raise WeakPasswordError("That password repeats too few characters.")


def _derive(
    password: str,
    salt: bytes,
    *,
    n: int = SCRYPT_N,
    r: int = SCRYPT_R,
    p: int = SCRYPT_P,
) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=KEY_BYTES)


#: A small list rather than a large one. The length rule does most of the work;
#: this catches the handful people still try first.
_COMMON = frozenset(
    {
        "password",
        "password1",
        "password123",
        "12345678",
        "123456789",
        "1234567890",
        "qwertyuiop",
        "letmein123",
        "welcome123",
        "admin12345",
        "iloveyou1",
        "caguard123",
        "changeme123",
        "abcdefghij",
    }
)
