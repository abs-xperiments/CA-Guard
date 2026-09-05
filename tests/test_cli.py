from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from caguard.cli import app

runner = CliRunner()


def test_generate_writes_ledger_truth_and_manifest(tmp_path: Path) -> None:
    result = runner.invoke(app, ["generate", "--vouchers", "300", "--out", str(tmp_path)])
    assert result.exit_code == 0, result.output

    written = {p.name for p in tmp_path.iterdir()}
    stem = "acme-in_fy2024-25_seed20250906"
    assert written == {f"{stem}.parquet", f"{stem}.truth.json", f"{stem}.manifest.json"}

    manifest = json.loads((tmp_path / f"{stem}.manifest.json").read_text())
    # A target, not an exact count: an invoice and its settlement are one event
    # and two vouchers, and the statutory remittances depend on what accrued.
    assert 300 <= manifest["vouchers"] <= 400
    assert len(manifest["content_sha256"]) == 64


def test_generate_refuses_an_unrealistic_anomaly_rate(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["generate", "--vouchers", "300", "--anomaly-rate", "0.5", "--out", str(tmp_path)]
    )
    assert result.exit_code != 0


def test_columns_reports_a_usable_mapping(tmp_path: Path) -> None:
    path = tmp_path / "tally.csv"
    path.write_text("Date,Particulars,Vch No.,Debit,Credit\n2024-04-01,Cash,V1,100,0\n")
    result = runner.invoke(app, ["columns", str(path)])
    assert result.exit_code == 0
    assert "Mapping is usable" in result.output
    assert "voucher_id" in result.output


def test_columns_names_what_is_missing(tmp_path: Path) -> None:
    path = tmp_path / "odd.csv"
    path.write_text("Colour,Size\nred,large\n")
    result = runner.invoke(app, ["columns", str(path)])
    assert "Missing required" in result.output


def test_ingest_on_a_missing_file_exits_cleanly(tmp_path: Path) -> None:
    result = runner.invoke(app, ["ingest", str(tmp_path / "nope.csv")])
    assert result.exit_code == 1
    assert "File not found" in result.output
