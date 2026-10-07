"""Tests for the local API: the whole path a reviewer takes.

Upload a ledger, get a prioritised queue, open a finding, read its explanation,
record a decision, export the report. Plus the two properties that matter beyond
the happy path: it works with no model installed, and it does not expose a
client's ledger on the network.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from caguard.api.app import create_app
from caguard.benchmark.generator import GeneratorConfig, generate


@pytest.fixture(scope="module")
def ledger_csv() -> bytes:
    lines = generate(GeneratorConfig(seed=101, n_vouchers=600)).lines
    buffer = io.StringIO()
    lines.to_csv(buffer, index=False)
    return buffer.getvalue().encode()


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    """A signed-in client.

    Every route that touches a ledger requires a session, so the fixture creates
    the first account. That the routes are actually protected is asserted in
    `test_auth.py`, not re-asserted here.
    """
    client = TestClient(create_app(tmp_path / "review.db"))
    response = client.post(
        "/api/auth/signup",
        json={
            "email": "reviewer@example.com",
            "name": "Reviewer",
            "password": "a-long-enough-passphrase",
        },
    )
    assert response.status_code == 200, response.text
    return client


@pytest.fixture
def opened(client: TestClient, ledger_csv: bytes) -> dict:
    response = client.post(
        "/api/engagements", files={"file": ("ledger.csv", ledger_csv, "text/csv")}
    )
    assert response.status_code == 200, response.text
    return response.json()


# --- the happy path ----------------------------------------------------------


def test_health_reports_the_model_position(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["model"] == "none"
    assert body["model_available"] is False


def test_upload_returns_a_prioritised_queue(opened: dict) -> None:
    assert opened["flagged"] > 0
    assert opened["flagged"] < opened["total_vouchers"], "a queue is not the whole ledger"

    priorities = [f["priority"] for f in opened["findings"]]
    assert priorities == sorted(priorities, reverse=True), "queue is not ranked"


def test_every_finding_carries_what_a_reviewer_needs(opened: dict) -> None:
    for finding in opened["findings"][:10]:
        assert finding["amount_display"].startswith("₹")
        assert finding["concerns"]
        assert finding["signals"]
        assert finding["line_ids"], "no link back to the ledger"
        assert finding["evidence"]["summary"]
        assert finding["status"] == "not yet reviewed"


def test_signals_are_ordered_by_contribution(opened: dict) -> None:
    """The reviewer should read the biggest reason first."""
    for finding in opened["findings"][:10]:
        contributions = [s["contribution"] for s in finding["signals"]]
        assert contributions == sorted(contributions, reverse=True)


def test_opening_the_same_ledger_twice_reuses_the_engagement(
    client: TestClient, ledger_csv: bytes, opened: dict
) -> None:
    again = client.post(
        "/api/engagements", files={"file": ("ledger.csv", ledger_csv, "text/csv")}
    ).json()
    assert again["engagement"]["id"] == opened["engagement"]["id"]
    assert len(client.get("/api/engagements").json()) == 1


def test_finding_detail(client: TestClient, opened: dict) -> None:
    engagement = opened["engagement"]["id"]
    voucher = opened["findings"][0]["voucher_id"]
    body = client.get(f"/api/engagements/{engagement}/findings/{voucher}").json()
    assert body["voucher_id"] == voucher
    assert body["evidence"]["completeness"] <= 1.0


def test_explanation_works_without_a_model(client: TestClient, opened: dict) -> None:
    """The interface must never look broken because no AI is installed."""
    engagement = opened["engagement"]["id"]
    voucher = opened["findings"][0]["voucher_id"]
    body = client.get(f"/api/engagements/{engagement}/findings/{voucher}/explanation").json()
    assert body["source"] == "deterministic"
    assert body["text"].strip()
    assert "CA-Guard" in body["provenance"]


def test_recording_a_decision(client: TestClient, opened: dict) -> None:
    engagement = opened["engagement"]["id"]
    voucher = opened["findings"][0]["voucher_id"]
    response = client.post(
        f"/api/engagements/{engagement}/decisions",
        json={"voucher_id": voucher, "action": "accept"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["sequence"] == 1

    queue = client.get(f"/api/engagements/{engagement}/queue").json()
    updated = next(f for f in queue["findings"] if f["voucher_id"] == voucher)
    assert updated["status"] == "accept"
    assert queue["states"]["accept"] == 1


def test_rejecting_without_a_reason_is_refused(client: TestClient, opened: dict) -> None:
    engagement = opened["engagement"]["id"]
    voucher = opened["findings"][0]["voucher_id"]
    response = client.post(
        f"/api/engagements/{engagement}/decisions",
        json={"voucher_id": voucher, "action": "reject"},
    )
    assert response.status_code == 422
    assert "needs a reason" in response.json()["detail"]


def test_the_trail_keeps_a_change_of_mind(client: TestClient, opened: dict) -> None:
    engagement = opened["engagement"]["id"]
    voucher = opened["findings"][0]["voucher_id"]
    for payload in (
        {"action": "investigate"},
        {"action": "reject", "note": "Traced to the signed lease"},
    ):
        client.post(
            f"/api/engagements/{engagement}/decisions",
            json={"voucher_id": voucher, **payload},
        )

    trail = client.get(
        f"/api/engagements/{engagement}/trail", params={"voucher_id": voucher}
    ).json()
    assert [entry["action"] for entry in trail] == ["investigate", "reject"]


def test_report_exports_cover_every_finding(client: TestClient, opened: dict) -> None:
    engagement = opened["engagement"]["id"]
    csv = client.get(f"/api/engagements/{engagement}/report.csv")
    assert csv.status_code == 200
    assert csv.headers["content-type"].startswith("text/csv")
    assert len(csv.text.strip().splitlines()) == opened["flagged"] + 1  # + header

    page = client.get(f"/api/engagements/{engagement}/report.html")
    assert page.status_code == 200
    assert "not conclusions" in page.text, "the report must not read as an accusation"
    for finding in opened["findings"][:5]:
        assert finding["voucher_id"] in page.text


# --- failure states ----------------------------------------------------------


def test_an_unknown_engagement_explains_itself(client: TestClient) -> None:
    response = client.get("/api/engagements/nope/queue")
    assert response.status_code == 404
    assert "no such engagement" in response.json()["detail"]


def test_an_unknown_voucher_is_a_404(client: TestClient, opened: dict) -> None:
    engagement = opened["engagement"]["id"]
    assert client.get(f"/api/engagements/{engagement}/findings/NOPE").status_code == 404


def test_an_unreadable_upload_gives_a_readable_error(client: TestClient) -> None:
    response = client.post(
        "/api/engagements", files={"file": ("notes.docx", b"nonsense", "text/plain")}
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    # Names the file the user chose, says what is accepted, and what did not happen.
    assert "notes.docx" in detail
    assert ".xlsx" in detail
    assert "Nothing was saved" in detail


def test_an_empty_upload_is_refused(client: TestClient) -> None:
    response = client.post("/api/engagements", files={"file": ("empty.csv", b"a,b\n", "text/csv")})
    assert response.status_code == 400
