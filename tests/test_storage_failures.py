"""When the database cannot be written, the reviewer is told — and nothing is half-saved.

Phase 7 reliability. A read-only volume, a full disk or a lock held by another
program all reached the reviewer as a bare "Internal Server Error".
"""

from __future__ import annotations

import io
import os
import sqlite3
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from caguard.api.app import create_app
from caguard.benchmark.generator import GeneratorConfig, generate


@pytest.fixture
def opened(tmp_path: Path) -> tuple[TestClient, Path, str, str]:
    store = tmp_path / "review.db"
    client = TestClient(create_app(store), raise_server_exceptions=False)
    body = {"email": "r@example.com", "name": "R", "password": "long-enough-pass"}
    assert client.post("/api/auth/signup", json=body).status_code == 200
    buffer = io.StringIO()
    generate(GeneratorConfig(seed=31, n_vouchers=250)).lines.to_csv(buffer, index=False)
    queue = client.post(
        "/api/engagements", files={"file": ("l.csv", buffer.getvalue().encode(), "text/csv")}
    ).json()
    return client, store, queue["engagement"]["id"], queue["findings"][0]["voucher_id"]


def _decide(client: TestClient, engagement: str, voucher: str):
    return client.post(
        f"/api/engagements/{engagement}/decisions",
        json={"voucher_id": voucher, "action": "accept"},
    )


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file permissions")
def test_a_read_only_database_is_explained_and_saves_nothing(
    opened: tuple[TestClient, Path, str, str],
) -> None:
    client, store, engagement, voucher = opened
    store.chmod(0o444)
    store.parent.chmod(0o555)
    try:
        response = _decide(client, engagement, voucher)
    finally:
        store.parent.chmod(0o755)
        store.chmod(0o644)

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "could not write to its database" in detail
    assert "Nothing was saved" in detail and "Error reference:" in detail
    assert client.get(f"/api/engagements/{engagement}/trail").json() == []
    assert client.get(f"/api/engagements/{engagement}/queue").status_code == 200


def test_a_database_locked_by_another_program_is_explained(
    opened: tuple[TestClient, Path, str, str],
) -> None:
    client, store, engagement, voucher = opened
    holder = sqlite3.connect(store, check_same_thread=False, isolation_level=None)
    holder.execute("BEGIN EXCLUSIVE")
    try:
        result: dict[str, object] = {}
        worker = threading.Thread(
            target=lambda: result.update(response=_decide(client, engagement, voucher))
        )
        worker.start()
        worker.join(timeout=30)
    finally:
        holder.execute("ROLLBACK")
        holder.close()

    response = result["response"]
    assert response.status_code == 503  # type: ignore[attr-defined]
    # Once the lock is gone, the same decision goes through.
    assert _decide(client, engagement, voucher).status_code == 200
