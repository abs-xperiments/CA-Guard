"""Sign up, sign in, sign out.

Everything a firm needs to control who can open a client's ledger, with no
external identity provider and no account with anyone.

The one design decision worth stating: **the reviewer recorded against a
decision comes from the session, never from the request body.** Before accounts
existed, the name came from a text box, which meant an audit trail anybody could
sign with anybody's name. A client is entitled to better than that.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from caguard.auth import sessions
from caguard.auth.policy import signup_policy
from caguard.auth.users import AuthError, User, UserStore

#: Cookies are same-site and http-only, so a script cannot read them and a
#: cross-site request cannot send them. `secure` is decided per request: a
#: self-hosted install runs on plain http over loopback, and refusing to set the
#: cookie there would make the product unusable on the machine it is built for.
COOKIE_KWARGS = {"httponly": True, "samesite": "lax", "path": "/"}


class SignupIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3)
    name: str = Field(min_length=1)
    password: str = Field(min_length=1)
    invite_code: str | None = None


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    display_name: str
    is_admin: bool
    created_at: datetime

    @classmethod
    def build(cls, user: User) -> UserOut:
        return cls(
            id=user.id,
            email=user.email,
            name=user.name,
            display_name=user.display_name,
            is_admin=user.is_admin,
            created_at=user.created_at,
        )


class SignupStateOut(BaseModel):
    """What the sign-up page should offer, before anyone has typed anything."""

    state: str
    needs_invite: bool
    explanation: str
    any_users: bool


def build_auth_router(users: UserStore, data_dir: Path, signing_key: bytes) -> APIRouter:
    router = APIRouter(prefix="/api/auth", tags=["auth"])

    def policy():
        return signup_policy(data_dir, has_users=not users.is_empty)

    @router.get("/signup-state", response_model=SignupStateOut)
    def signup_state() -> SignupStateOut:
        current = policy()
        return SignupStateOut(
            state=current.state.value,
            needs_invite=not current.is_open,
            explanation=current.describe(),
            any_users=not users.is_empty,
        )

    @router.post("/signup", response_model=UserOut)
    def signup(body: SignupIn, response: Response, request: Request) -> UserOut:
        current = policy()
        try:
            current.check(body.invite_code)
            user = users.create(body.email, body.name, body.password)
        except (AuthError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc

        _set_session(response, request, signing_key, user)
        return UserOut.build(user)

    @router.post("/login", response_model=UserOut)
    def login(body: LoginIn, response: Response, request: Request) -> UserOut:
        try:
            user = users.authenticate(body.email, body.password)
        except AuthError as exc:
            # 401, not 422: this is "we do not know you", not "your input is malformed".
            raise HTTPException(401, str(exc)) from exc

        _set_session(response, request, signing_key, user)
        return UserOut.build(user)

    @router.post("/logout")
    def logout(response: Response) -> dict[str, bool]:
        response.delete_cookie(sessions.COOKIE_NAME, path="/")
        return {"ok": True}

    @router.get("/me", response_model=UserOut)
    def me(user: User = Depends(_require_user(users, signing_key))) -> UserOut:
        return UserOut.build(user)

    return router


def _set_session(response: Response, request: Request, signing_key: bytes, user: User) -> None:
    secure = request.url.scheme == "https"
    response.set_cookie(
        sessions.COOKIE_NAME,
        sessions.issue(signing_key, user.id, user.email),
        max_age=sessions.SESSION_SECONDS,
        secure=secure,
        **COOKIE_KWARGS,  # pyright: ignore[reportArgumentType]
    )


def _require_user(users: UserStore, signing_key: bytes):
    """Build the dependency that protects every route touching a ledger."""

    def dependency(request: Request) -> User:
        cookie = request.cookies.get(sessions.COOKIE_NAME)
        try:
            token = sessions.read(signing_key, cookie)
        except sessions.InvalidSessionError as exc:
            raise HTTPException(401, "Please sign in to continue.") from exc

        user = users.by_id(token.user_id)
        if user is None:
            # The account was removed while a cookie was still valid.
            raise HTTPException(401, "That account no longer exists.") from None
        return user

    return dependency


def current_user_dependency(users: UserStore, signing_key: bytes):
    """Public alias, so the application wires this in one obvious place."""
    return _require_user(users, signing_key)
