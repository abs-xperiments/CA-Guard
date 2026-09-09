"""Who is allowed to create an account.

This matters more than it looks. A self-hosted install in one firm's office can
let the first person sign up freely — there is nobody else on the network. A
deployment with a public URL cannot: open signup means strangers uploading files
and consuming whatever it is running on.

So the rule adapts to the situation rather than being configured wrongly by
default. The first account is always free, because somebody has to be able to
get in. After that, signup needs an invite code, and if none is configured, it
is closed.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

INVITE_ENV = "CAGUARD_INVITE_CODE"
INVITE_FILENAME = "invite.code"


class SignupState(StrEnum):
    #: No accounts yet. The first person to sign up becomes the administrator.
    BOOTSTRAP = "bootstrap"
    #: Accounts exist; a colleague needs the firm's invite code.
    INVITE_ONLY = "invite_only"


@dataclass(frozen=True)
class SignupPolicy:
    state: SignupState
    invite_code: str | None

    @property
    def is_open(self) -> bool:
        return self.state is SignupState.BOOTSTRAP

    def check(self, offered: str | None) -> None:
        """Raise if this person may not create an account."""
        from caguard.auth.users import AuthError

        if self.is_open:
            return
        if not self.invite_code:
            raise AuthError("Sign-ups are closed. Ask an existing user to set an invite code.")
        if not offered or not secrets.compare_digest(offered.strip(), self.invite_code):
            raise AuthError("That invite code is not correct.")

    def describe(self) -> str:
        if self.is_open:
            return (
                "This is a new installation, so the first account you create "
                "becomes the administrator."
            )
        return "An invite code from your firm is needed to create an account."


def signup_policy(data_dir: Path, *, has_users: bool) -> SignupPolicy:
    """Work out the signup rule for this installation.

    The invite code comes from the environment where one is set — which is how a
    deployment would supply it — and is otherwise generated once and written
    beside the database, so a self-hosted firm gets a code without inventing one.
    """
    if not has_users:
        return SignupPolicy(SignupState.BOOTSTRAP, None)

    configured = os.environ.get(INVITE_ENV, "").strip()
    if configured:
        return SignupPolicy(SignupState.INVITE_ONLY, configured)

    return SignupPolicy(SignupState.INVITE_ONLY, _local_invite_code(data_dir))


def _local_invite_code(data_dir: Path) -> str:
    """A code generated once for this installation, printed when the server starts."""
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / INVITE_FILENAME
    if path.exists():
        return path.read_text().strip()

    code = secrets.token_urlsafe(9)
    path.write_text(code)
    path.chmod(0o600)
    return code
