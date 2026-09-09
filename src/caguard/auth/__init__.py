"""Who is using CA-Guard, and proving it.

A reviewer's identity is written into the audit trail, so it has to come from
somewhere better than a text box on the page — which is what it came from
before. It now comes from a signed session.

Everything here is local: accounts live in the same SQLite file as the
decisions, sessions are signed with a key generated on first run, and no
external identity provider is involved. A firm installing CA-Guard needs no
account with anyone.
"""

from caguard.auth.passwords import WeakPasswordError, hash_password, verify_password
from caguard.auth.policy import SignupPolicy, signup_policy
from caguard.auth.sessions import COOKIE_NAME, InvalidSessionError, issue, read
from caguard.auth.users import AuthError, User, UserStore

__all__ = [
    "COOKIE_NAME",
    "AuthError",
    "InvalidSessionError",
    "SignupPolicy",
    "User",
    "UserStore",
    "WeakPasswordError",
    "hash_password",
    "issue",
    "read",
    "signup_policy",
    "verify_password",
]
