"""The sample ledger: a synthetic book to try CA-Guard with, never the evaluation set."""

from __future__ import annotations

import gzip
import io
import sys
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from make_sample_ledger import OUT, SAMPLE_SEED, VOUCHERS, tally_style

from caguard.api.app import create_app
from caguard.benchmark.generator import GeneratorConfig, generate
from caguard.evaluation.benchmark import HELD_OUT_SEEDS, TUNING_SEEDS


def test_the_sample_is_never_a_benchmark_ledger() -> None:
    """A demo visitor must not be shown the held-out evaluation set, or the tuning set."""
    assert SAMPLE_SEED not in HELD_OUT_SEEDS
    assert SAMPLE_SEED not in TUNING_SEEDS


def test_the_committed_sample_is_exactly_what_the_script_makes() -> None:
    """So it cannot drift from the seed and format it claims to have."""
    lines = generate(GeneratorConfig(seed=SAMPLE_SEED, n_vouchers=VOUCHERS)).lines
    buffer = io.StringIO()
    tally_style(lines).to_csv(buffer, index=False)
    assert gzip.decompress(OUT.read_bytes()).decode() == buffer.getvalue()


def test_the_sample_reads_cleanly_as_a_tally_export(tmp_path: Path) -> None:
    """Every row used, and no "this file has no document column" warning."""
    client = TestClient(create_app(tmp_path / "review.db"))
    body = {"email": "r@example.com", "name": "R", "password": "long-enough-pass"}
    client.post("/api/auth/signup", json=body)
    sample = client.get("/api/sample-ledger").content
    intake = client.post(
        "/api/engagements", files={"file": ("sample.csv", sample, "text/csv")}
    ).json()["intake"]
    assert intake["rows_used"] == intake["rows_read"]
    assert intake["notes"] == []
    assert "document_ref" in intake["mapped"].values()
    assert "posted_at" in intake["mapped"].values()


def test_the_sample_needs_a_session_and_is_the_same_every_time(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "review.db"))
    assert client.get("/api/sample-ledger").status_code == 401

    body = {"email": "r@example.com", "name": "R", "password": "long-enough-pass"}
    assert client.post("/api/auth/signup", json=body).status_code == 200
    first = client.get("/api/sample-ledger")
    second = client.get("/api/sample-ledger")

    assert first.status_code == 200
    assert first.content == second.content
    assert "synthetic" in first.headers["content-disposition"]
    frame = pd.read_csv(io.StringIO(first.text))
    assert {"Voucher No", "Date", "Ledger", "Debit", "Credit", "Doc Ref"} <= set(frame.columns)


def test_the_sample_opens_as_a_review(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "review.db"))
    body = {"email": "r@example.com", "name": "R", "password": "long-enough-pass"}
    client.post("/api/auth/signup", json=body)
    sample = client.get("/api/sample-ledger").content

    queue = client.post(
        "/api/engagements",
        files={"file": ("CA-Guard sample ledger (synthetic).csv", sample, "text/csv")},
    )
    assert queue.status_code == 200
    assert queue.json()["flagged"] > 0
