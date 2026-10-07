"""The uploaded files themselves: kept exactly, traceable, recoverable, deletable.

Phase 2 of the completion plan. The questions these tests answer are the ones a
reviewer asks: is the file I download the file I uploaded? Which row of it did
this finding come from? Is my engagement still there after a restart? And when I
delete a client's file, is it actually gone?
"""

from __future__ import annotations

import hashlib
import io
import sqlite3
from pathlib import Path
from urllib.parse import unquote

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from caguard.api.app import create_app
from caguard.benchmark.generator import GeneratorConfig, generate
from caguard.review.engagement import ledger_hash
from caguard.review.store import SCHEMA_VERSION, ReviewStore

FIXTURES = Path(__file__).parent / "fixtures"
INVITE = "firm-invite-code"
TEST_PASSPHRASE = "a-long-enough-passphrase"


@pytest.fixture(scope="module")
def ledger() -> pd.DataFrame:
    return generate(GeneratorConfig(seed=515, n_vouchers=300)).lines


@pytest.fixture(scope="module")
def csv_bytes(ledger: pd.DataFrame) -> bytes:
    buffer = io.StringIO()
    ledger.to_csv(buffer, index=False)
    return buffer.getvalue().encode()


@pytest.fixture(scope="module")
def xlsx_bytes(ledger: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    ledger.to_excel(buffer, index=False)
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def _invite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAGUARD_INVITE_CODE", INVITE)


def _signed_in(store: Path, email: str = "admin@firm.in") -> TestClient:
    client = TestClient(create_app(store))
    body = {"email": email, "name": email.split("@")[0], "password": TEST_PASSPHRASE}
    response = client.post("/api/auth/signup", json={**body, "invite_code": INVITE})
    if response.status_code != 200:  # the account exists already: sign in instead
        response = client.post(
            "/api/auth/login", json={"email": email, "password": TEST_PASSPHRASE}
        )
    assert response.status_code == 200, response.text
    return client


@pytest.fixture
def store(tmp_path: Path) -> Path:
    return tmp_path / "review.db"


@pytest.fixture
def client(store: Path) -> TestClient:
    return _signed_in(store)


def _upload(client: TestClient, name: str, payload: bytes) -> dict:
    response = client.post("/api/engagements", files={"file": (name, payload, "text/plain")})
    assert response.status_code == 200, response.text
    return response.json()


def _sources(client: TestClient, engagement_id: str) -> list[dict]:
    response = client.get(f"/api/engagements/{engagement_id}/sources")
    assert response.status_code == 200, response.text
    return response.json()


def _vault(store: Path) -> list[Path]:
    directory = store.parent / "sources"
    return sorted(directory.iterdir()) if directory.exists() else []


# --- the original, exactly ----------------------------------------------------


@pytest.mark.parametrize("kind", ["csv", "xlsx", "xls", "parquet"])
def test_the_downloaded_original_is_byte_identical(
    client: TestClient, ledger: pd.DataFrame, csv_bytes: bytes, xlsx_bytes: bytes, kind: str
) -> None:
    if kind == "csv":
        payload = csv_bytes
    elif kind == "xlsx":
        payload = xlsx_bytes
    elif kind == "xls":
        payload = (FIXTURES / "legacy_ledger.xls").read_bytes()
    else:
        buffer = io.BytesIO()
        ledger.to_parquet(buffer, index=False)
        payload = buffer.getvalue()

    queue = _upload(client, f"Client Books FY25.{kind}", payload)
    engagement = queue["engagement"]["id"]
    (source,) = _sources(client, engagement)

    response = client.get(f"/api/engagements/{engagement}/sources/{source['id']}/original")

    assert response.status_code == 200
    assert response.content == payload
    expected = hashlib.sha256(payload).hexdigest()
    assert source["sha256"] == expected
    assert response.headers["x-content-sha256"] == expected
    # RFC 5987 encoding (filename*=utf-8''...), which browsers decode.
    assert f"Client Books FY25.{kind}" in unquote(response.headers["content-disposition"])
    assert response.headers["x-content-type-options"] == "nosniff"


def test_source_metadata_describes_the_upload(client: TestClient, csv_bytes: bytes) -> None:
    queue = _upload(client, "books.csv", csv_bytes)
    (source,) = _sources(client, queue["engagement"]["id"])

    assert source["filename"] == "books.csv"
    assert source["file_type"] == "CSV"
    assert source["size_bytes"] == len(csv_bytes)
    assert source["uploaded_by"] == "admin"
    assert source["rows_used"] == queue["intake"]["rows_used"]
    assert source["available"] is True


def test_the_stored_original_is_readable_only_by_its_owner(
    client: TestClient, store: Path, csv_bytes: bytes
) -> None:
    _upload(client, "books.csv", csv_bytes)
    (stored,) = _vault(store)
    assert stored.stat().st_mode & 0o777 == 0o600
    assert stored.parent.stat().st_mode & 0o777 == 0o700


def test_a_file_that_could_not_be_analysed_is_not_kept(client: TestClient, store: Path) -> None:
    response = client.post(
        "/api/engagements", files={"file": ("broken.csv", b"\x00\x01binary", "text/csv")}
    )
    assert response.status_code == 400
    assert "Nothing was saved" in response.json()["detail"]
    assert _vault(store) == []


def test_the_same_file_twice_is_stored_once(
    client: TestClient, store: Path, csv_bytes: bytes
) -> None:
    first = _upload(client, "books.csv", csv_bytes)
    second = _upload(client, "books.csv", csv_bytes)

    assert first["engagement"]["id"] == second["engagement"]["id"]
    assert len(_sources(client, first["engagement"]["id"])) == 1
    assert len(_vault(store)) == 1


def test_the_same_book_in_two_formats_is_one_engagement_with_two_files(
    client: TestClient, csv_bytes: bytes, xlsx_bytes: bytes
) -> None:
    first = _upload(client, "books.csv", csv_bytes)
    second = _upload(client, "books.xlsx", xlsx_bytes)

    assert first["engagement"]["id"] == second["engagement"]["id"]
    names = {s["filename"] for s in _sources(client, first["engagement"]["id"])}
    assert names == {"books.csv", "books.xlsx"}


# --- traceability: finding -> line -> row of the file ---------------------------


def test_every_line_of_a_finding_points_at_its_row_in_the_file(
    client: TestClient, csv_bytes: bytes
) -> None:
    queue = _upload(client, "books.csv", csv_bytes)
    engagement = queue["engagement"]["id"]
    voucher = queue["findings"][0]["voucher_id"]

    finding = client.get(f"/api/engagements/{engagement}/findings/{voucher}").json()
    assert finding["source"]["filename"] == "books.csv"
    assert finding["lines"], "a single finding carries its ledger lines"

    rows = csv_bytes.decode().splitlines()  # rows[0] is the header, i.e. row 1
    for line in finding["lines"]:
        assert line["account_name"], "lines carry account names, not just codes"
        row_text = rows[line["source_row"] - 1]
        assert row_text.startswith(line["line_id"] + ","), (line["source_row"], row_text)

        preview = client.get(
            f"/api/engagements/{engagement}/sources/{finding['source']['id']}/preview",
            params={"offset": line["source_row"] - 2, "limit": 1},
        ).json()
        assert preview["rows"][0]["row"] == line["source_row"]
        assert line["line_id"] in preview["rows"][0]["values"]


def test_row_numbers_survive_blank_lines_in_the_file(client: TestClient, csv_bytes: bytes) -> None:
    """pandas skips blank lines by default, which would shift every later row."""
    rows = csv_bytes.decode().splitlines()
    with_gap = "\n".join([*rows[:10], "", "", *rows[10:]]) + "\n"
    queue = _upload(client, "gappy.csv", with_gap.encode())
    engagement = queue["engagement"]["id"]

    physical = with_gap.splitlines()
    for item in queue["findings"][:5]:
        finding = client.get(f"/api/engagements/{engagement}/findings/{item['voucher_id']}")
        for line in finding.json()["lines"]:
            assert physical[line["source_row"] - 1].startswith(line["line_id"] + ",")


def test_the_queue_does_not_carry_every_ledger_line(client: TestClient, csv_bytes: bytes) -> None:
    queue = _upload(client, "books.csv", csv_bytes)
    assert all(f["lines"] == [] for f in queue["findings"])


def test_provenance_does_not_change_the_ledger_hash(ledger: pd.DataFrame) -> None:
    """Otherwise adding source rows would have re-keyed every existing engagement."""
    with_rows = ledger.assign(source_row=range(2, len(ledger) + 2))
    assert ledger_hash(with_rows) == ledger_hash(ledger)


def test_preview_pages_are_bounded(client: TestClient, csv_bytes: bytes) -> None:
    queue = _upload(client, "books.csv", csv_bytes)
    engagement = queue["engagement"]["id"]
    (source,) = _sources(client, engagement)
    url = f"/api/engagements/{engagement}/sources/{source['id']}/preview"

    assert client.get(url, params={"limit": 10_000}).status_code == 422
    page = client.get(url, params={"offset": 0, "limit": 5}).json()
    assert [r["row"] for r in page["rows"]] == [2, 3, 4, 5, 6]
    assert page["total_rows"] == len(csv_bytes.decode().splitlines()) - 1


# --- the engagement survives a restart ------------------------------------------


def test_an_engagement_reopens_after_a_restart_with_identical_findings(
    store: Path, csv_bytes: bytes
) -> None:
    before = _signed_in(store)
    queue = _upload(before, "books.csv", csv_bytes)
    engagement = queue["engagement"]["id"]
    voucher = queue["findings"][0]["voucher_id"]
    before.post(
        f"/api/engagements/{engagement}/decisions",
        json={"voucher_id": voucher, "action": "investigate", "note": "ask for the invoice"},
    )

    after = _signed_in(store)  # a fresh process: nothing in memory
    reopened = after.get(f"/api/engagements/{engagement}/queue")

    assert reopened.status_code == 200, reopened.text
    body = reopened.json()
    assert [(f["voucher_id"], f["priority"]) for f in body["findings"]] == [
        (f["voucher_id"], f["priority"]) for f in queue["findings"]
    ]
    assert body["intake"]["rows_used"] == queue["intake"]["rows_used"]
    assert body["findings"][0]["status"] == "investigate"


def test_an_engagement_from_before_files_were_kept_says_so(store: Path, csv_bytes: bytes) -> None:
    client = _signed_in(store)
    engagement = _upload(client, "books.csv", csv_bytes)["engagement"]["id"]
    with sqlite3.connect(store) as connection:  # as if opened by an earlier build
        connection.execute("DELETE FROM source_files")

    response = _signed_in(store).get(f"/api/engagements/{engagement}/queue")
    assert response.status_code == 409
    assert "before CA-Guard kept original files" in response.json()["detail"]


def test_a_tampered_original_is_not_served(
    client: TestClient, store: Path, csv_bytes: bytes
) -> None:
    engagement = _upload(client, "books.csv", csv_bytes)["engagement"]["id"]
    (source,) = _sources(client, engagement)
    (stored,) = _vault(store)
    stored.write_bytes(csv_bytes.replace(b"V0", b"X0", 1))

    response = client.get(f"/api/engagements/{engagement}/sources/{source['id']}/original")
    assert response.status_code == 409
    assert "no longer matches" in response.json()["detail"]


# --- deletion --------------------------------------------------------------------


def test_only_an_administrator_can_delete_an_original(store: Path, csv_bytes: bytes) -> None:
    admin = _signed_in(store)
    engagement = _upload(admin, "books.csv", csv_bytes)["engagement"]["id"]
    (source,) = _sources(admin, engagement)

    colleague = _signed_in(store, "colleague@firm.in")
    response = colleague.delete(f"/api/engagements/{engagement}/sources/{source['id']}")
    assert response.status_code == 403
    assert len(_vault(store)) == 1


def test_deleting_an_original_removes_the_bytes_and_keeps_the_trail(
    store: Path, csv_bytes: bytes
) -> None:
    client = _signed_in(store)
    queue = _upload(client, "books.csv", csv_bytes)
    engagement = queue["engagement"]["id"]
    voucher = queue["findings"][0]["voucher_id"]
    client.post(
        f"/api/engagements/{engagement}/decisions",
        json={"voucher_id": voucher, "action": "accept"},
    )
    (source,) = _sources(client, engagement)

    deleted = client.delete(f"/api/engagements/{engagement}/sources/{source['id']}")

    assert deleted.status_code == 200
    assert _vault(store) == [], "the file must actually be gone from disk"
    (listed,) = _sources(client, engagement)
    assert listed["available"] is False and listed["deleted_by"] == "admin"
    assert (
        client.get(f"/api/engagements/{engagement}/sources/{source['id']}/original").status_code
        == 410
    )

    reopened = client.get(f"/api/engagements/{engagement}/queue")
    assert reopened.status_code == 409
    assert "was deleted" in reopened.json()["detail"]
    assert len(client.get(f"/api/engagements/{engagement}/trail").json()) == 1


def test_shared_bytes_survive_until_the_last_record_is_deleted(
    client: TestClient, store: Path, csv_bytes: bytes
) -> None:
    """Two engagements can hold the same bytes only via different records; here,
    the same file re-uploaded after deletion must be stored again."""
    engagement = _upload(client, "books.csv", csv_bytes)["engagement"]["id"]
    (source,) = _sources(client, engagement)
    client.delete(f"/api/engagements/{engagement}/sources/{source['id']}")
    assert _vault(store) == []

    _upload(client, "books.csv", csv_bytes)
    assert len(_vault(store)) == 1
    assert client.get(f"/api/engagements/{engagement}/queue").status_code == 200


# --- isolation and hostile input ---------------------------------------------------


def test_a_file_cannot_be_reached_through_another_engagement(
    client: TestClient, csv_bytes: bytes
) -> None:
    first = _upload(client, "a.csv", csv_bytes)["engagement"]["id"]
    other = generate(GeneratorConfig(seed=516, n_vouchers=250)).lines
    buffer = io.StringIO()
    other.to_csv(buffer, index=False)
    second = _upload(client, "b.csv", buffer.getvalue().encode())["engagement"]["id"]
    (source,) = _sources(client, first)

    for suffix in ("original", "preview"):
        url = f"/api/engagements/{second}/sources/{source['id']}/{suffix}"
        assert client.get(url).status_code == 404


@pytest.mark.parametrize(
    "hostile", ["../../../etc/passwd.csv", "..\\..\\windows\\ledger.csv", 'a"b\r\nX: y.csv']
)
def test_a_hostile_filename_never_reaches_a_path_or_a_header(
    client: TestClient, store: Path, csv_bytes: bytes, hostile: str
) -> None:
    engagement = _upload(client, hostile, csv_bytes)["engagement"]["id"]
    (source,) = _sources(client, engagement)
    (stored,) = _vault(store)

    assert stored.parent == store.parent / "sources"
    assert stored.name == f"{source['sha256']}.csv"
    response = client.get(f"/api/engagements/{engagement}/sources/{source['id']}/original")
    assert response.status_code == 200
    disposition = response.headers["content-disposition"]
    decoded = unquote(disposition)
    assert "\r" not in decoded and "\n" not in decoded and "/" not in decoded
    assert "\\" not in decoded


def test_source_routes_require_a_session(client: TestClient, csv_bytes: bytes) -> None:
    engagement = _upload(client, "books.csv", csv_bytes)["engagement"]["id"]
    (source,) = _sources(client, engagement)
    anonymous = TestClient(client.app)
    base = f"/api/engagements/{engagement}/sources"
    for method, url in [
        ("get", base),
        ("get", f"{base}/{source['id']}/original"),
        ("get", f"{base}/{source['id']}/preview"),
        ("delete", f"{base}/{source['id']}"),
    ]:
        assert getattr(anonymous, method)(url).status_code == 401, url


# --- the database upgrade -----------------------------------------------------------

_V1_SCHEMA = """
CREATE TABLE schema_version (version INTEGER NOT NULL);
INSERT INTO schema_version VALUES (1);
CREATE TABLE engagements (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, entity_id TEXT NOT NULL,
    fiscal_year TEXT NOT NULL, source_name TEXT NOT NULL, content_sha256 TEXT NOT NULL,
    voucher_count INTEGER NOT NULL, opened_at TEXT NOT NULL
);
CREATE TABLE decisions (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    engagement_id TEXT NOT NULL REFERENCES engagements(id), voucher_id TEXT NOT NULL,
    action TEXT NOT NULL, reviewer TEXT NOT NULL, note TEXT, adjusted_band TEXT,
    decided_at TEXT NOT NULL
);
INSERT INTO engagements VALUES
    ('e1', 'ACME FY25', 'ACME', 'FY2024-25', 'old.csv', 'abcdef0123456789', 10,
     '2026-09-01T10:00:00+00:00');
INSERT INTO decisions (engagement_id, voucher_id, action, reviewer, note, decided_at)
    VALUES ('e1', 'V1', 'reject', 'A Reviewer', 'invoice seen and agreed',
            '2026-09-01T11:00:00+00:00');
"""


def test_a_version_1_database_upgrades_and_keeps_its_decisions(tmp_path: Path) -> None:
    path = tmp_path / "review.db"
    with sqlite3.connect(path) as connection:
        connection.executescript(_V1_SCHEMA)

    store = ReviewStore(path)

    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT version FROM schema_version").fetchone() == (
            SCHEMA_VERSION,
        )
    (decision,) = store.trail("e1")
    assert decision.note == "invoice seen and agreed"
    assert store.sources("e1") == []
    ReviewStore(path)  # opening again is a no-op, not a second migration


def test_a_database_from_a_newer_build_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "review.db"
    ReviewStore(path)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION + 1,))
    with pytest.raises(RuntimeError, match="Refusing to guess"):
        ReviewStore(path)
