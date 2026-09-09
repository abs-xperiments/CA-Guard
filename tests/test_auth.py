"""Tests for accounts, sessions, and the fact that nothing is reachable without one.

The property that matters most is not "logging in works". It is that **the
reviewer written into the audit trail comes from the session** — before accounts
existed it came from a text box, which meant a trail anyone could sign with
anyone's name. A client is entitled to better.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from caguard.api.app import create_app
from caguard.auth import sessions
from caguard.auth.passwords import (
    WeakPasswordError,
    check_strength,
    hash_password,
    verify_password,
)
from caguard.auth.policy import SignupState, signup_policy
from caguard.auth.users import AuthError, UserStore
from caguard.benchmark.generator import GeneratorConfig, generate

GOOD_PASSWORD = "a-long-enough-passphrase"


@pytest.fixture(scope="module")
def ledger_csv() -> bytes:
    lines = generate(GeneratorConfig(seed=101, n_vouchers=400)).lines
    buffer = io.StringIO()
    lines.to_csv(buffer, index=False)
    return buffer.getvalue().encode()


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(tmp_path / "review.db"))


@pytest.fixture
def signed_in(client: TestClient) -> TestClient:
    response = client.post(
        "/api/auth/signup",
        json={
            "email": "abirami@example.com",
            "name": "Abirami",
            "password": GOOD_PASSWORD,
        },
    )
    assert response.status_code == 200, response.text
    return client


# --- passwords ----------------------------------------------------------------


def test_a_password_round_trips() -> None:
    stored = hash_password(GOOD_PASSWORD)
    assert verify_password(GOOD_PASSWORD, stored)
    assert not verify_password("something else entirely", stored)


def test_the_password_is_never_stored_in_the_clear() -> None:
    stored = hash_password(GOOD_PASSWORD)
    assert GOOD_PASSWORD not in stored
    assert stored.startswith("scrypt$")


def test_two_hashes_of_the_same_password_differ() -> None:
    """Salted, so a stolen database does not reveal who shares a password."""
    assert hash_password(GOOD_PASSWORD) != hash_password(GOOD_PASSWORD)


def test_a_corrupt_hash_fails_closed() -> None:
    assert not verify_password(GOOD_PASSWORD, "nonsense")
    assert not verify_password(GOOD_PASSWORD, "scrypt$bad$bad$bad$bad$bad")


@pytest.mark.parametrize("password", ["short", "password123", "aaaaaaaaaaaa"])
def test_weak_passwords_are_refused(password: str) -> None:
    with pytest.raises(WeakPasswordError):
        check_strength(password)


def test_the_length_rule_is_explained_not_just_enforced() -> None:
    with pytest.raises(WeakPasswordError, match="short phrase you will remember"):
        check_strength("abc")


# --- sessions -----------------------------------------------------------------


def test_a_session_round_trips(tmp_path: Path) -> None:
    key = sessions.load_or_create_key(tmp_path)
    token = sessions.issue(key, "user-1", "a@b.com")
    assert sessions.read(key, token).user_id == "user-1"


def test_a_tampered_session_is_refused(tmp_path: Path) -> None:
    key = sessions.load_or_create_key(tmp_path)
    token = sessions.issue(key, "user-1", "a@b.com")
    with pytest.raises(sessions.InvalidSessionError, match="signature"):
        sessions.read(key, token[:-4] + "aaaa")


def test_a_session_signed_with_another_key_is_refused(tmp_path: Path) -> None:
    token = sessions.issue(sessions.load_or_create_key(tmp_path / "a"), "u", "a@b.com")
    other = sessions.load_or_create_key(tmp_path / "b")
    with pytest.raises(sessions.InvalidSessionError):
        sessions.read(other, token)


def test_an_expired_session_is_refused(tmp_path: Path) -> None:
    key = sessions.load_or_create_key(tmp_path)
    with pytest.raises(sessions.InvalidSessionError, match="expired"):
        sessions.read(key, sessions.issue(key, "u", "a@b.com", seconds=-1))


def test_the_signing_key_is_owner_only(tmp_path: Path) -> None:
    sessions.load_or_create_key(tmp_path)
    mode = (tmp_path / sessions.KEY_FILENAME).stat().st_mode & 0o777
    assert mode == 0o600


def test_the_signing_key_is_stable_across_restarts(tmp_path: Path) -> None:
    """Otherwise every restart would log the whole firm out."""
    assert sessions.load_or_create_key(tmp_path) == sessions.load_or_create_key(tmp_path)


# --- accounts -----------------------------------------------------------------


def test_the_first_account_is_the_administrator(tmp_path: Path) -> None:
    store = UserStore(tmp_path / "review.db")
    first = store.create("a@example.com", "First", GOOD_PASSWORD)
    second = store.create("b@example.com", "Second", GOOD_PASSWORD)
    assert first.is_admin
    assert not second.is_admin


def test_email_is_case_insensitive(tmp_path: Path) -> None:
    store = UserStore(tmp_path / "review.db")
    store.create("Abirami@Example.com", "Abirami", GOOD_PASSWORD)
    assert store.authenticate("ABIRAMI@EXAMPLE.COM", GOOD_PASSWORD)


def test_duplicate_accounts_are_refused(tmp_path: Path) -> None:
    store = UserStore(tmp_path / "review.db")
    store.create("a@example.com", "A", GOOD_PASSWORD)
    with pytest.raises(AuthError, match="already exists"):
        store.create("a@example.com", "A again", GOOD_PASSWORD)


def test_a_wrong_password_gives_the_same_message_as_an_unknown_address(
    tmp_path: Path,
) -> None:
    """So the endpoint cannot be used to discover which addresses have accounts."""
    store = UserStore(tmp_path / "review.db")
    store.create("a@example.com", "A", GOOD_PASSWORD)

    with pytest.raises(AuthError) as wrong:
        store.authenticate("a@example.com", "not-the-right-password")
    with pytest.raises(AuthError) as unknown:
        store.authenticate("nobody@example.com", GOOD_PASSWORD)
    assert str(wrong.value) == str(unknown.value)


def test_a_malformed_email_is_refused(tmp_path: Path) -> None:
    store = UserStore(tmp_path / "review.db")
    with pytest.raises(AuthError, match="email address"):
        store.create("not-an-email", "A", GOOD_PASSWORD)


# --- who may sign up ----------------------------------------------------------


def test_the_first_signup_is_open(tmp_path: Path) -> None:
    policy = signup_policy(tmp_path, has_users=False)
    assert policy.state is SignupState.BOOTSTRAP
    policy.check(None)  # must not raise


def test_later_signups_need_an_invite(tmp_path: Path) -> None:
    """A public URL with open signup is strangers uploading files."""
    policy = signup_policy(tmp_path, has_users=True)
    assert policy.state is SignupState.INVITE_ONLY
    with pytest.raises(AuthError, match="invite code"):
        policy.check(None)
    policy.check(policy.invite_code)  # the right code works


def test_an_invite_code_can_come_from_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Which is how a deployment supplies one."""
    monkeypatch.setenv("CAGUARD_INVITE_CODE", "firm-code-2026")
    policy = signup_policy(tmp_path, has_users=True)
    assert policy.invite_code == "firm-code-2026"
    policy.check("firm-code-2026")


# --- nothing is reachable without signing in ----------------------------------


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/engagements"),
        ("get", "/api/engagements/x/queue"),
        ("get", "/api/engagements/x/findings/V1"),
        ("get", "/api/engagements/x/trail"),
        ("get", "/api/engagements/x/report.csv"),
        ("get", "/api/engagements/x/report.html"),
        ("post", "/api/engagements/x/decisions"),
        ("get", "/api/auth/me"),
    ],
)
def test_every_ledger_route_requires_a_session(client: TestClient, method: str, path: str) -> None:
    call = getattr(client, method)
    response = call(path, json={}) if method == "post" else call(path)
    assert response.status_code == 401, f"{path} was reachable without signing in"


def test_upload_requires_a_session(client: TestClient, ledger_csv: bytes) -> None:
    response = client.post(
        "/api/engagements", files={"file": ("ledger.csv", ledger_csv, "text/csv")}
    )
    assert response.status_code == 401


def test_health_is_public(client: TestClient) -> None:
    """So a container health check does not need credentials."""
    assert client.get("/api/health").status_code == 200


# --- the flow -----------------------------------------------------------------


def test_signup_then_use_the_application(signed_in: TestClient, ledger_csv: bytes) -> None:
    me = signed_in.get("/api/auth/me").json()
    assert me["email"] == "abirami@example.com"
    assert me["is_admin"] is True

    upload = signed_in.post(
        "/api/engagements", files={"file": ("ledger.csv", ledger_csv, "text/csv")}
    )
    assert upload.status_code == 200
    assert upload.json()["flagged"] > 0


def test_signing_out_ends_access(signed_in: TestClient) -> None:
    assert signed_in.post("/api/auth/logout").status_code == 200
    assert signed_in.get("/api/auth/me").status_code == 401


def test_logging_in_again_restores_access(signed_in: TestClient) -> None:
    signed_in.post("/api/auth/logout")
    response = signed_in.post(
        "/api/auth/login",
        json={"email": "abirami@example.com", "password": GOOD_PASSWORD},
    )
    assert response.status_code == 200
    assert signed_in.get("/api/auth/me").status_code == 200


def test_a_wrong_password_is_401_not_422(signed_in: TestClient) -> None:
    signed_in.post("/api/auth/logout")
    response = signed_in.post(
        "/api/auth/login",
        json={"email": "abirami@example.com", "password": "wrong-password-here"},
    )
    assert response.status_code == 401
    assert "do not match" in response.json()["detail"]


def test_the_session_cookie_is_http_only(client: TestClient) -> None:
    """A script on the page must not be able to read it."""
    response = client.post(
        "/api/auth/signup",
        json={"email": "a@example.com", "name": "A", "password": GOOD_PASSWORD},
    )
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie.replace("Samesite", "SameSite")


def test_a_weak_password_is_refused_at_signup(client: TestClient) -> None:
    response = client.post(
        "/api/auth/signup",
        json={"email": "a@example.com", "name": "A", "password": "short"},
    )
    assert response.status_code == 422
    assert "at least" in response.json()["detail"]


def test_the_signup_page_is_told_which_state_it_is_in(client: TestClient) -> None:
    fresh = client.get("/api/auth/signup-state").json()
    assert fresh["state"] == "bootstrap"
    assert fresh["needs_invite"] is False
    assert "first account" in fresh["explanation"]

    client.post(
        "/api/auth/signup",
        json={"email": "a@example.com", "name": "A", "password": GOOD_PASSWORD},
    )
    after = client.get("/api/auth/signup-state").json()
    assert after["needs_invite"] is True


# --- the audit trail is signed by the session ---------------------------------


def test_the_reviewer_comes_from_the_session_not_the_request(
    signed_in: TestClient, ledger_csv: bytes
) -> None:
    """The whole reason accounts exist.

    Even if a caller sends someone else's name in the body, the trail records
    who was actually signed in.
    """
    queue = signed_in.post(
        "/api/engagements", files={"file": ("ledger.csv", ledger_csv, "text/csv")}
    ).json()
    engagement = queue["engagement"]["id"]
    voucher = queue["findings"][0]["voucher_id"]

    response = signed_in.post(
        f"/api/engagements/{engagement}/decisions",
        json={
            "voucher_id": voucher,
            "action": "accept",
            "reviewer": "Somebody Else",  # ignored; not part of the schema
        },
    )
    # Sending an unexpected field is rejected outright rather than silently used.
    assert response.status_code == 422

    accepted = signed_in.post(
        f"/api/engagements/{engagement}/decisions",
        json={"voucher_id": voucher, "action": "accept"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["reviewer"] == "Abirami"

    trail = signed_in.get(f"/api/engagements/{engagement}/trail").json()
    assert trail[0]["reviewer"] == "Abirami"


def test_a_configured_invite_code_protects_even_the_first_account(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Closes a race a public deployment would otherwise have.

    Between a deployment going live and its owner signing up, the
    first-account-is-free rule would let a passer-by become the administrator.
    Where an invite code is configured, it is required from the very first
    account, so that window does not exist.
    """
    monkeypatch.setenv("CAGUARD_INVITE_CODE", "firm-code-2026")
    policy = signup_policy(tmp_path, has_users=False)

    assert policy.state is SignupState.INVITE_ONLY
    assert policy.protects_first_account
    with pytest.raises(AuthError, match="invite code"):
        policy.check(None)
    policy.check("firm-code-2026")


def test_a_local_install_still_bootstraps_freely(tmp_path: Path) -> None:
    """No code configured means a firm can just install it and start."""
    policy = signup_policy(tmp_path, has_users=False)
    assert policy.is_open
    policy.check(None)
