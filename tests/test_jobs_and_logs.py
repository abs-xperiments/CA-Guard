"""Background analysis with visible stages, and logs that never hold client data.

Phase 5 of the completion plan. An upload becomes a job a reviewer can watch;
a failure says what happened and that nothing was kept; and every event the
product logs along the whole review path is checked for ledger content.
"""

from __future__ import annotations

import io
import logging
import time
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import caguard.api.workspace as workspace_module
from caguard.api.app import create_app
from caguard.benchmark.generator import GeneratorConfig, generate
from caguard.observability import REDACTED, event

INVITE = "firm-invite-code"
PASS = "a-long-enough-passphrase"


@pytest.fixture(scope="module")
def ledger() -> pd.DataFrame:
    return generate(GeneratorConfig(seed=909, n_vouchers=400)).lines


@pytest.fixture(scope="module")
def csv_bytes(ledger: pd.DataFrame) -> bytes:
    buffer = io.StringIO()
    ledger.to_csv(buffer, index=False)
    return buffer.getvalue().encode()


@pytest.fixture(autouse=True)
def _invite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAGUARD_INVITE_CODE", INVITE)


def _client(store: Path, email: str = "partner@firm.in") -> TestClient:
    client = TestClient(create_app(store))
    body = {"email": email, "name": email.split("@")[0], "password": PASS, "invite_code": INVITE}
    assert client.post("/api/auth/signup", json=body).status_code == 200
    return client


def _wait(client: TestClient, job_id: str, seconds: float = 60) -> dict:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["state"] in {"done", "failed"}:
            return job
        time.sleep(0.05)
    raise AssertionError("the job did not finish")


def _start(client: TestClient, name: str, payload: bytes):
    return client.post("/api/uploads", files={"file": (name, payload, "text/csv")})


# --- the job ------------------------------------------------------------------------


def test_an_upload_returns_a_job_that_finishes_with_an_engagement(
    tmp_path: Path, csv_bytes: bytes
) -> None:
    client = _client(tmp_path / "review.db")
    started = _start(client, "books.csv", csv_bytes)

    assert started.status_code == 202
    assert started.json()["state"] in {"queued", "running", "done"}

    job = _wait(client, started.json()["id"])
    assert job["state"] == "done", job
    assert job["error"] is None
    assert [stage["state"] for stage in job["stages"]] == ["done"] * 4
    queue = client.get(f"/api/engagements/{job['engagement_id']}/queue")
    assert queue.status_code == 200 and queue.json()["flagged"] > 0


def test_a_slow_analysis_shows_which_stage_it_has_reached(
    tmp_path: Path, csv_bytes: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = workspace_module.build_findings

    def slow(*args, **kwargs):
        time.sleep(1.0)
        return real(*args, **kwargs)

    monkeypatch.setattr(workspace_module, "build_findings", slow)
    client = _client(tmp_path / "review.db")
    job_id = _start(client, "books.csv", csv_bytes).json()["id"]

    seen: set[str] = set()
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        current = [s["key"] for s in job["stages"] if s["state"] == "current"]
        seen.update(current)
        if job["state"] == "done":
            break
        time.sleep(0.05)

    assert "analysing" in seen, f"saw only {seen}"


def test_an_unreadable_file_fails_the_job_in_plain_words_and_keeps_nothing(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path / "review.db")
    job = _wait(client, _start(client, "broken.csv", b"\x00\x01binary").json()["id"])

    assert job["state"] == "failed"
    assert "broken.csv" in job["error"] and "Nothing was saved" in job["error"]
    sources = tmp_path / "sources"
    assert not sources.exists() or not any(sources.iterdir())
    assert not list(tmp_path.glob("upload-*")), "the received file is removed"


def test_an_unexpected_failure_gives_a_reference_not_internals(
    tmp_path: Path, csv_bytes: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    def explode(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("internal detail that must not reach the reviewer")

    monkeypatch.setattr(workspace_module, "build_findings", explode)
    client = _client(tmp_path / "review.db")
    job = _wait(client, _start(client, "books.csv", csv_bytes).json()["id"])

    assert job["state"] == "failed"
    assert "Error reference:" in job["error"]
    assert "internal detail" not in job["error"]


def test_a_wrong_file_type_is_refused_before_any_job_starts(tmp_path: Path) -> None:
    client = _client(tmp_path / "review.db")
    response = client.post("/api/uploads", files={"file": ("notes.docx", b"x", "text/plain")})
    assert response.status_code == 400
    assert "notes.docx" in response.json()["detail"]


def test_a_job_is_visible_only_to_the_account_that_started_it(
    tmp_path: Path, csv_bytes: bytes
) -> None:
    store = tmp_path / "review.db"
    partner = _client(store)
    job_id = _start(partner, "books.csv", csv_bytes).json()["id"]
    _wait(partner, job_id)

    colleague = TestClient(partner.app)
    body = {"email": "article@firm.in", "name": "article", "password": PASS, "invite_code": INVITE}
    assert colleague.post("/api/auth/signup", json=body).status_code == 200
    assert colleague.get(f"/api/jobs/{job_id}").status_code == 404
    assert TestClient(partner.app).get(f"/api/jobs/{job_id}").status_code == 401


# --- the event helper -------------------------------------------------------------------


def test_events_keep_numbers_and_identifiers_and_redact_free_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("caguard.test")
    with caplog.at_level(logging.INFO, logger="caguard"):
        event(
            logger,
            "sample",
            engagement="70c9653cda9d1d4b",
            rows=8916,
            seconds=1.23456,
            ok=True,
            narration="Prior period expense recorded",
            account="Miscellaneous Expenses",
            filename="Sharma Traders FY25.xlsx",
        )
    line = caplog.records[-1].getMessage()
    assert "engagement=70c9653cda9d1d4b" in line
    assert "rows=8916" in line and "seconds=1.235" in line and "ok=true" in line
    assert "Prior period" not in line and "Miscellaneous" not in line and "Sharma" not in line
    assert line.count(REDACTED) == 3


def test_a_field_cannot_change_the_log_level(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("caguard.test")
    with caplog.at_level(logging.INFO, logger="caguard"):
        event(logger, "sample", level="anything")  # a field, not the level
    assert caplog.records[-1].levelno == logging.INFO


# --- the whole review path, logged ----------------------------------------------------


def test_nothing_from_the_ledger_reaches_the_log_on_the_whole_review_path(
    tmp_path: Path, ledger: pd.DataFrame, csv_bytes: bytes, caplog: pytest.LogCaptureFixture
) -> None:
    """Upload, open, explain, report, download, delete — then read every log line."""
    client = _client(tmp_path / "review.db")
    with caplog.at_level(logging.DEBUG):
        job = _wait(client, _start(client, "Sharma Traders FY25.csv", csv_bytes).json()["id"])
        engagement = job["engagement_id"]
        base = f"/api/engagements/{engagement}"
        voucher = client.get(f"{base}/queue").json()["findings"][0]["voucher_id"]
        client.get(f"{base}/findings/{voucher}")
        client.get(f"{base}/findings/{voucher}/explanation")
        client.post(
            f"{base}/decisions",
            json={"voucher_id": voucher, "action": "reject", "note": "invoice seen and agreed"},
        )
        client.get(f"{base}/report.html")
        client.get(f"{base}/report.csv")
        (source,) = client.get(f"{base}/sources").json()
        client.get(f"{base}/sources/{source['id']}/original")
        client.delete(f"{base}/sources/{source['id']}")

    logged = "\n".join(
        record.getMessage() for record in caplog.records if record.name.startswith("caguard")
    )
    for expected in (
        "upload.received",
        "analysis.completed",
        "seconds_total=",
        "explanation.generated",
        "report.generated",
        "source.downloaded",
        "source.deleted",
    ):
        assert expected in logged, f"missing event {expected}"

    forbidden = {
        "Sharma Traders",
        "invoice seen and agreed",
        *ledger["narration"].dropna().astype(str).unique()[:200],
        *ledger["account_name"].dropna().astype(str).unique(),
        *ledger["created_by"].dropna().astype(str).unique(),
    }
    leaked = sorted(text for text in forbidden if len(text) > 3 and text in logged)
    assert not leaked, f"ledger content reached the log: {leaked[:5]}"
