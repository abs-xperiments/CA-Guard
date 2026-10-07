"""Uploads as they arrive from real offices, not as we would like them to.

Each test here pins a defect found in the 2026-10-07 audit by running the
product rather than reading it: files Excel on Windows actually writes, legacy
workbooks, a server that froze while it analysed, a temporary file two uploads
shared, and error messages that named files the user had never heard of.
"""

from __future__ import annotations

import io
import threading
import time
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import caguard.api.app as app_module
import caguard.api.workspace as workspace_module
from caguard.api.app import create_app
from caguard.benchmark.generator import GeneratorConfig, generate
from caguard.intake.readers import IntakeError, read_table

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def ledger() -> pd.DataFrame:
    return generate(GeneratorConfig(seed=303, n_vouchers=300)).lines


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    client = TestClient(create_app(tmp_path / "review.db"))
    response = client.post(
        "/api/auth/signup",
        json={"email": "r@example.com", "name": "Reviewer", "password": "long-enough-pass"},
    )
    assert response.status_code == 200, response.text
    return client


def _csv(frame: pd.DataFrame, encoding: str) -> bytes:
    buffer = io.StringIO()
    frame.to_csv(buffer, index=False)
    return buffer.getvalue().encode(encoding)


def _upload(client: TestClient, name: str, payload: bytes):
    return client.post("/api/engagements", files={"file": (name, payload, "text/csv")})


def _leftover_uploads(tmp_path: Path) -> list[Path]:
    return list(tmp_path.glob("upload-*")) + list(tmp_path.glob("_upload*"))


# --- encodings real offices produce -------------------------------------------


def test_a_windows_1252_csv_is_read_and_the_encoding_is_disclosed(
    client: TestClient, ledger: pd.DataFrame
) -> None:
    # "Café" is encoded differently in CP1252 and UTF-8, so this file is not
    # valid UTF-8 — exactly what Excel on an English Windows machine saves.
    frame = ledger.assign(narration=ledger["narration"].fillna("") + " Café")
    response = _upload(client, "books.csv", _csv(frame, "cp1252"))

    assert response.status_code == 200, response.text
    notes = response.json()["intake"]["notes"]
    assert any("CP1252" in note for note in notes)


def test_a_utf16_csv_is_read(client: TestClient, ledger: pd.DataFrame) -> None:
    response = _upload(client, "books.csv", _csv(ledger, "utf-16"))
    assert response.status_code == 200, response.text


def test_a_utf8_csv_carries_no_encoding_note(client: TestClient, ledger: pd.DataFrame) -> None:
    response = _upload(client, "books.csv", _csv(ledger, "utf-8"))
    assert response.status_code == 200
    assert not any("encoding" in n or "UTF-8" in n for n in response.json()["intake"]["notes"])


def test_a_real_legacy_xls_workbook_is_read(client: TestClient) -> None:
    payload = (FIXTURES / "legacy_ledger.xls").read_bytes()
    response = client.post(
        "/api/engagements",
        files={"file": ("ledger.xls", payload, "application/vnd.ms-excel")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["intake"]["rows_used"] == 636


# --- refusals that a reviewer can act on --------------------------------------


@pytest.mark.parametrize(
    ("name", "payload", "expected"),
    [
        ("empty.csv", b"", "is empty"),
        ("headers.csv", b"voucher_id,voucher_date\n", "no rows"),
        ("binary.csv", b"\x00\x01\x02garbage" * 50, "binary data"),
        ("renamed.xlsx", b"this is not a workbook", "could not be read as an Excel"),
    ],
)
def test_bad_files_are_refused_in_plain_language(
    client: TestClient, tmp_path: Path, name: str, payload: bytes, expected: str
) -> None:
    response = _upload(client, name, payload)

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert expected in detail
    assert name in detail, "the message must name the file the user chose"
    assert "Nothing was saved" in detail
    # The internal temporary file is an implementation detail; naming it in a
    # message only confuses the person reading it.
    assert "upload-" not in detail and "_upload" not in detail
    assert "Traceback" not in detail and "codec" not in detail
    assert not _leftover_uploads(tmp_path)


def test_an_oversized_upload_is_refused_and_leaves_nothing_behind(
    client: TestClient, tmp_path: Path, ledger: pd.DataFrame, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app_module, "MAX_UPLOAD_BYTES", 1024)
    monkeypatch.setattr(app_module, "UPLOAD_CHUNK_BYTES", 256)

    response = _upload(client, "big.csv", _csv(ledger, "utf-8"))

    assert response.status_code == 413
    assert "big.csv" in response.json()["detail"]
    assert not _leftover_uploads(tmp_path)


def test_a_successful_upload_leaves_no_temporary_file(
    client: TestClient, tmp_path: Path, ledger: pd.DataFrame
) -> None:
    assert _upload(client, "ok.csv", _csv(ledger, "utf-8")).status_code == 200
    assert not _leftover_uploads(tmp_path)


def test_an_unexpected_analysis_failure_gives_a_reference_not_an_exception(
    client: TestClient, ledger: pd.DataFrame, monkeypatch: pytest.MonkeyPatch
) -> None:
    def explode(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("internal detail that must not reach the user")

    monkeypatch.setattr(workspace_module, "build_findings", explode)
    response = _upload(client, "books.csv", _csv(ledger, "utf-8"))

    assert response.status_code == 500
    detail = response.json()["detail"]
    assert "Error reference:" in detail
    assert "internal detail" not in detail
    assert "Nothing was saved" in detail


def test_read_table_never_reports_the_internal_path(tmp_path: Path) -> None:
    hidden = tmp_path / "upload-abc123.csv"
    hidden.write_bytes(b"")
    with pytest.raises(IntakeError) as caught:
        read_table(hidden, display_name="Client ledger.csv")
    assert "Client ledger.csv" in str(caught.value)
    assert "upload-abc123" not in str(caught.value)


# --- the server stays responsive and uploads stay separate --------------------


def test_the_server_answers_while_a_ledger_is_being_analysed(
    client: TestClient, ledger: pd.DataFrame, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Analysis on the event loop froze every request until it finished."""
    real = workspace_module.build_findings

    def slow(*args, **kwargs):
        time.sleep(1.5)
        return real(*args, **kwargs)

    monkeypatch.setattr(workspace_module, "build_findings", slow)
    payload = _csv(ledger, "utf-8")
    worker = threading.Thread(target=_upload, args=(client, "slow.csv", payload))
    worker.start()
    time.sleep(0.3)  # let the upload reach the analysis

    started = time.perf_counter()
    health = client.get("/api/health")
    elapsed = time.perf_counter() - started
    worker.join()

    assert health.status_code == 200
    assert elapsed < 0.75, f"health took {elapsed:.2f}s while a ledger was analysed"


def test_simultaneous_uploads_of_different_ledgers_stay_separate(client: TestClient) -> None:
    """A shared temporary filename let one upload read another's ledger."""
    books = {
        f"client{seed}.csv": _csv(
            generate(GeneratorConfig(seed=seed, n_vouchers=250)).lines, "utf-8"
        )
        # Two: the most one account may have in flight (the limit is pinned in
        # test_a_third_concurrent_analysis_is_refused_politely).
        for seed in (404, 405)
    }
    results: dict[str, dict] = {}

    def send(name: str) -> None:
        response = _upload(client, name, books[name])
        assert response.status_code == 200, response.text
        results[name] = response.json()

    threads = [threading.Thread(target=send, args=(name,)) for name in books]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert set(results) == set(books)
    assert len({r["engagement"]["id"] for r in results.values()}) == 2
    for name, result in results.items():
        assert result["engagement"]["source_name"] == name


def test_health_does_not_disclose_workload(client: TestClient) -> None:
    """Health is public for container checks; it should say nothing about clients."""
    body = TestClient(client.app).get("/api/health").json()
    assert set(body) == {"status", "model", "model_available", "demo_mode"}


def test_a_failure_log_never_contains_ledger_values(
    client: TestClient,
    ledger: pd.DataFrame,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    marker = "NARRATION-THAT-MUST-NOT-BE-LOGGED"

    def explode(*_args: object, **_kwargs: object) -> None:
        raise ValueError(f"could not convert {marker!r}")

    monkeypatch.setattr(workspace_module, "build_findings", explode)
    with caplog.at_level("DEBUG"):
        response = _upload(client, "books.csv", _csv(ledger, "utf-8"))

    assert response.status_code == 500
    assert "analysis.failed" in caplog.text
    assert marker not in caplog.text


def test_a_third_concurrent_analysis_is_refused_politely(
    client: TestClient, ledger: pd.DataFrame, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One account may not tie up every worker, through either upload route."""
    release = threading.Event()
    real = workspace_module.build_findings

    def held(*args, **kwargs):
        release.wait(timeout=30)
        return real(*args, **kwargs)

    monkeypatch.setattr(workspace_module, "build_findings", held)
    payload = _csv(ledger, "utf-8")
    first = client.post("/api/uploads", files={"file": ("a.csv", payload, "text/csv")})
    second = client.post("/api/uploads", files={"file": ("b.csv", payload, "text/csv")})
    assert first.status_code == second.status_code == 202

    third_job = client.post("/api/uploads", files={"file": ("c.csv", payload, "text/csv")})
    third_sync = _upload(client, "d.csv", payload)
    release.set()

    for response in (third_job, third_sync):
        assert response.status_code == 429
        assert "already being analysed" in response.json()["detail"]
