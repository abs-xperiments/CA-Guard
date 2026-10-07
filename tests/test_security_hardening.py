"""Phase 6 hardening: hostile workbooks, response headers, and a quieter demo.

Each test here follows a probe run during the security review. The XML
entity bomb was already refused by Python's own parser — the test pins that so
a future change cannot quietly undo it. The zip bomb was not refused, and is now.
"""

from __future__ import annotations

import io
import time
import zipfile
from pathlib import Path

import openpyxl
import pytest
from fastapi.testclient import TestClient

import caguard.intake.readers as readers
from caguard.api.app import REPORT_CSP, create_app
from caguard.benchmark.generator import GeneratorConfig, generate
from caguard.intake.readers import IntakeError, read_table


def _workbook(payload_cell: str = "PAYLOAD") -> bytes:
    book = openpyxl.Workbook()
    sheet = book.active
    assert sheet is not None
    sheet["A1"] = "voucher_id"
    sheet["A2"] = payload_cell
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def _entity_bomb() -> bytes:
    """A workbook whose one cell expands to 10^9 characters through nested entities."""
    entities = "".join(
        f'<!ENTITY {chr(98 + i)} "{("&" + chr(97 + i) + ";") * 10}">' for i in range(8)
    )
    dtd = f'<?xml version="1.0"?>\n<!DOCTYPE x [<!ENTITY a "AAAAAAAAAA">{entities}]>\n'
    source = zipfile.ZipFile(io.BytesIO(_workbook()))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in source.namelist():
            data = source.read(name)
            if b"PAYLOAD" in data:
                text = data.decode()
                body = text.split("?>", 1)[1] if text.startswith("<?xml") else text
                data = (dtd + body.replace("PAYLOAD", "&i;")).encode()
            archive.writestr(name, data)
    return out.getvalue()


# --- hostile workbooks ---------------------------------------------------------------


def test_an_xml_entity_bomb_is_refused_quickly(tmp_path: Path) -> None:
    path = tmp_path / "bomb.xlsx"
    path.write_bytes(_entity_bomb())
    started = time.perf_counter()
    with pytest.raises(IntakeError, match="could not be read as an Excel workbook"):
        read_table(path)
    assert time.perf_counter() - started < 5


def test_a_workbook_that_unpacks_too_large_is_refused_before_parsing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(readers, "MAX_UNPACKED_BYTES", 1024)
    path = tmp_path / "big.xlsx"
    path.write_bytes(_workbook())
    with pytest.raises(IntakeError, match="would unpack to"):
        read_table(path, display_name="Client ledger.xlsx")


def test_a_renamed_file_posing_as_xlsx_gets_a_plain_answer(tmp_path: Path) -> None:
    path = tmp_path / "fake.xlsx"
    path.write_bytes(b"this is a csv, really\nvoucher_id\n1\n")
    with pytest.raises(IntakeError, match=r"not a valid \.xlsx file"):
        read_table(path)


# --- response headers ------------------------------------------------------------------


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.delenv("CAGUARD_DEMO", raising=False)
    client = TestClient(create_app(tmp_path / "review.db"))
    body = {"email": "r@example.com", "name": "R", "password": "long-enough-pass"}
    assert client.post("/api/auth/signup", json=body).status_code == 200
    return client


def test_every_api_response_carries_the_baseline_headers(client: TestClient) -> None:
    for response in (client.get("/api/health"), client.get("/api/engagements")):
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert response.headers["cache-control"] == "no-store"


def test_the_report_may_not_run_scripts_or_load_anything(client: TestClient) -> None:
    buffer = io.StringIO()
    generate(GeneratorConfig(seed=11, n_vouchers=250)).lines.to_csv(buffer, index=False)
    queue = client.post(
        "/api/engagements", files={"file": ("l.csv", buffer.getvalue().encode(), "text/csv")}
    ).json()
    report = client.get(f"/api/engagements/{queue['engagement']['id']}/report.html")

    assert report.headers["content-security-policy"] == REPORT_CSP
    assert "default-src 'none'" in REPORT_CSP and "script-src" not in REPORT_CSP
    assert "<script" not in report.text.lower()


def test_api_docs_exist_locally_and_not_on_the_demo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CAGUARD_DEMO", raising=False)
    local = TestClient(create_app(tmp_path / "local.db"))
    assert local.get("/docs").status_code == 200

    monkeypatch.setenv("CAGUARD_DEMO", "1")
    demo = TestClient(create_app(tmp_path / "demo.db"))
    assert demo.get("/docs").status_code == 404
    assert demo.get("/openapi.json").status_code == 404
