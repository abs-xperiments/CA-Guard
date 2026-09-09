"""User accounts, and where they live.

A reviewer's identity matters more here than in most applications, because it is
written into the audit trail. Before accounts existed, the reviewer's name came
from a text box on the page — anyone could type anyone's name, which is not an
audit trail so much as a suggestion. It now comes from the session.

Accounts live in the same SQLite file as the review decisions, so a firm still
has exactly one file to back up.
"""

from __future__ import annotations

import re
import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from caguard.auth.passwords import hash_password, verify_password

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name          TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin      INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL
);
"""


class AuthError(ValueError):
    """Something the user can fix. The message is shown to them."""


@dataclass(frozen=True)
class User:
    id: str
    email: str
    name: str
    is_admin: bool
    created_at: datetime

    @property
    def display_name(self) -> str:
        return self.name or self.email.split("@")[0]


class UserStore:
    """Accounts, in the same database as the decisions they will sign."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, isolation_level=None)
        connection.row_factory = sqlite3.Row
        return connection

    # --- reading -------------------------------------------------------------

    def count(self) -> int:
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT COUNT(*) AS n FROM users").fetchone()
        return int(row["n"])

    @property
    def is_empty(self) -> bool:
        """Whether this is a fresh installation with nobody signed up yet."""
        return self.count() == 0

    def by_email(self, email: str) -> User | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email.strip(),)
            ).fetchone()
        return _user_from(row) if row else None

    def by_id(self, user_id: str) -> User | None:
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return _user_from(row) if row else None

    def all(self) -> list[User]:
        with closing(self._connect()) as connection:
            rows = connection.execute("SELECT * FROM users ORDER BY created_at").fetchall()
        return [_user_from(row) for row in rows]

    # --- writing -------------------------------------------------------------

    def create(self, email: str, name: str, password: str) -> User:
        """Register an account. The first one created is the administrator."""
        email = _clean_email(email)
        name = name.strip()
        if not name:
            raise AuthError("Please give your name, so decisions can be attributed.")

        if self.by_email(email) is not None:
            # Deliberately explicit. Hiding this on a self-hosted tool for one
            # firm protects nobody and confuses the person trying to sign in.
            raise AuthError("An account already exists with that email address.")

        user = User(
            id=uuid.uuid4().hex,
            email=email,
            name=name,
            is_admin=self.is_empty,
            created_at=datetime.now(UTC),
        )
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO users (id, email, name, password_hash, is_admin, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    user.id,
                    user.email,
                    user.name,
                    hash_password(password),
                    int(user.is_admin),
                    user.created_at.isoformat(),
                ),
            )
        return user

    def authenticate(self, email: str, password: str) -> User:
        """Check an email and password.

        The same message is returned whether the address is unknown or the
        password is wrong, so this endpoint cannot be used to discover which
        addresses have accounts.
        """
        user = self.by_email(_clean_email(email))
        stored = self._password_hash(user.id) if user else None

        if user is None or stored is None or not verify_password(password, stored):
            raise AuthError("That email address and password do not match.")
        return user

    def set_password(self, user_id: str, password: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (hash_password(password), user_id),
            )

    def _password_hash(self, user_id: str) -> str | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT password_hash FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return row["password_hash"] if row else None


def _clean_email(email: str) -> str:
    cleaned = email.strip().lower()
    if not EMAIL_PATTERN.match(cleaned):
        raise AuthError("That does not look like an email address.")
    return cleaned


def _user_from(row: sqlite3.Row) -> User:
    return User(
        id=row["id"],
        email=row["email"],
        name=row["name"],
        is_admin=bool(row["is_admin"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )
