"""Sign-in protections a public deployment needs and a local one should not notice."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from caguard.api.app import create_app
from caguard.api.auth_routes import reached_over_https
from caguard.auth.throttle import MAX_FAILURES, LoginThrottle

# --- the throttle on its own ---------------------------------------------------


class FakeClock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


def test_the_throttle_allows_mistakes_up_to_the_limit() -> None:
    throttle = LoginThrottle(clock=FakeClock())
    for _ in range(MAX_FAILURES - 1):
        throttle.failed("a@firm.in")
    assert throttle.retry_after("a@firm.in") == 0


def test_the_throttle_locks_after_the_limit_and_releases_after_the_window() -> None:
    clock = FakeClock()
    throttle = LoginThrottle(clock=clock, window_seconds=900)
    for _ in range(MAX_FAILURES):
        throttle.failed("a@firm.in")

    assert throttle.retry_after("a@firm.in") > 0
    clock.now += 901
    assert throttle.retry_after("a@firm.in") == 0


def test_the_throttle_is_per_account_and_case_insensitive() -> None:
    throttle = LoginThrottle(clock=FakeClock())
    for _ in range(MAX_FAILURES):
        throttle.failed("A@Firm.in ")
    assert throttle.retry_after("a@firm.in") > 0
    assert throttle.retry_after("someone.else@firm.in") == 0


def test_a_successful_sign_in_clears_the_count() -> None:
    throttle = LoginThrottle(clock=FakeClock())
    for _ in range(MAX_FAILURES - 1):
        throttle.failed("a@firm.in")
    throttle.succeeded("a@firm.in")
    throttle.failed("a@firm.in")
    assert throttle.retry_after("a@firm.in") == 0


# --- the throttle in the API ---------------------------------------------------


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("CAGUARD_INVITE_CODE", "firm-invite-code")
    client = TestClient(create_app(tmp_path / "review.db"))
    for email in ("owner@firm.in", "colleague@firm.in"):
        code = "firm-invite-code"
        response = client.post(
            "/api/auth/signup",
            json={
                "email": email,
                "name": email.split("@")[0],
                "password": "the-right-passphrase",
                "invite_code": code,
            },
        )
        assert response.status_code == 200, response.text
    client.cookies.clear()
    return client


def _login(client: TestClient, email: str, password: str):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_repeated_wrong_passwords_are_refused_with_a_wait(client: TestClient) -> None:
    for _ in range(MAX_FAILURES):
        assert _login(client, "owner@firm.in", "wrong").status_code == 401

    blocked = _login(client, "owner@firm.in", "the-right-passphrase")
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0
    assert "Try again" in blocked.json()["detail"]


def test_one_locked_account_does_not_lock_the_firm(client: TestClient) -> None:
    """Behind the proxy every request comes from loopback, so this must be per account."""
    for _ in range(MAX_FAILURES):
        _login(client, "owner@firm.in", "wrong")
    assert _login(client, "colleague@firm.in", "the-right-passphrase").status_code == 200


# --- Secure cookies behind the workspace proxy ----------------------------------


def _request(*, scheme: str = "http", peer: str = "127.0.0.1", proto: str | None = None):
    headers = [(b"x-forwarded-proto", proto.encode())] if proto else []
    return Request(
        {
            "type": "http",
            "scheme": scheme,
            "client": (peer, 50000),
            "headers": headers,
            "method": "POST",
            "path": "/api/auth/login",
            "server": ("127.0.0.1", 8000),
            "query_string": b"",
        }
    )


@pytest.fixture(autouse=True)
def _no_forced_secure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CAGUARD_SECURE_COOKIES", raising=False)


def test_plain_local_http_does_not_demand_a_secure_cookie() -> None:
    """A self-hosted install on http://127.0.0.1 must still be able to sign in."""
    assert reached_over_https(_request()) is False


def test_https_reported_by_our_own_proxy_is_believed() -> None:
    assert reached_over_https(_request(proto="https")) is True


def test_a_forwarded_header_from_elsewhere_is_not_believed() -> None:
    assert reached_over_https(_request(peer="203.0.113.9", proto="https")) is False


def test_a_deployment_can_force_secure_cookies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAGUARD_SECURE_COOKIES", "1")
    assert reached_over_https(_request()) is True
