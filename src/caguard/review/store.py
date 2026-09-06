"""Where review decisions live: one local SQLite file, append-only.

**Append-only.** A review trail that can be edited is not a review trail. Every
decision is a new row and nothing is ever updated or deleted. A reviewer
changing their mind is itself a fact worth keeping — the sequence of views is
often more informative than the final one.

**Findings are not stored.** Re-running the same ledger at the same version
reproduces them exactly, which is what the content hash is for. A stored copy
would drift from what the code now says, and then nobody would know which was
right. Decisions reference the voucher; the finding is recomputed.

**No server, no port, no credentials.** The privacy story is local processing,
and a single file is something a firm can back up by copying it.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path

from caguard.review.decisions import Decision, ReviewAction
from caguard.review.engagement import Engagement

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS engagements (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    entity_id       TEXT NOT NULL,
    fiscal_year     TEXT NOT NULL,
    source_name     TEXT NOT NULL,
    content_sha256  TEXT NOT NULL,
    voucher_count   INTEGER NOT NULL,
    opened_at       TEXT NOT NULL
);

-- Append-only. No UPDATE and no DELETE is issued against this table anywhere
-- in the codebase, and tests assert that the trail only ever grows.
CREATE TABLE IF NOT EXISTS decisions (
    sequence        INTEGER PRIMARY KEY AUTOINCREMENT,
    engagement_id   TEXT NOT NULL REFERENCES engagements(id),
    voucher_id      TEXT NOT NULL,
    action          TEXT NOT NULL,
    reviewer        TEXT NOT NULL,
    note            TEXT,
    adjusted_band   TEXT,
    decided_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS decisions_by_engagement
    ON decisions (engagement_id, voucher_id, sequence);
"""


class ReviewStore:
    """The local review database. Safe to open repeatedly."""

    def __init__(self, path: Path | str = "data/review.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    # --- lifecycle -----------------------------------------------------------

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            yield connection
        finally:
            connection.close()

    def _migrate(self) -> None:
        """Create the schema if it is not there. Idempotent by design."""
        with self._connect() as connection:
            connection.executescript(_SCHEMA)
            current = connection.execute("SELECT version FROM schema_version").fetchone()
            if current is None:
                connection.execute(
                    "INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,)
                )
            elif current["version"] != SCHEMA_VERSION:
                raise RuntimeError(
                    f"{self.path} was written by schema version {current['version']}, "
                    f"but this build expects {SCHEMA_VERSION}. Refusing to guess."
                )

    # --- engagements ---------------------------------------------------------

    def open_engagement(self, engagement: Engagement) -> Engagement:
        """Record an engagement, or return the one already stored under this id."""
        existing = self.engagement(engagement.id)
        if existing is not None:
            return existing

        with self._connect() as connection:
            connection.execute(
                """INSERT INTO engagements
                   (id, name, entity_id, fiscal_year, source_name,
                    content_sha256, voucher_count, opened_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    engagement.id,
                    engagement.name,
                    engagement.entity_id,
                    engagement.fiscal_year,
                    engagement.source_name,
                    engagement.content_sha256,
                    engagement.voucher_count,
                    engagement.opened_at.isoformat(),
                ),
            )
        return engagement

    def engagement(self, engagement_id: str) -> Engagement | None:
        with (
            self._connect() as connection,
            closing(
                connection.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,))
            ) as cursor,
        ):
            row = cursor.fetchone()
        return _engagement_from(row) if row else None

    def engagements(self) -> list[Engagement]:
        with (
            self._connect() as connection,
            closing(
                connection.execute("SELECT * FROM engagements ORDER BY opened_at DESC")
            ) as cursor,
        ):
            return [_engagement_from(row) for row in cursor.fetchall()]

    # --- decisions -----------------------------------------------------------

    def record(self, decision: Decision) -> Decision:
        """Append a decision. Nothing is ever overwritten."""
        if self.engagement(decision.engagement_id) is None:
            raise KeyError(f"no engagement {decision.engagement_id!r} is open")

        with self._connect() as connection:
            cursor = connection.execute(
                """INSERT INTO decisions
                   (engagement_id, voucher_id, action, reviewer, note,
                    adjusted_band, decided_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    decision.engagement_id,
                    decision.voucher_id,
                    decision.action.value,
                    decision.reviewer,
                    decision.note,
                    decision.adjusted_band.value if decision.adjusted_band else None,
                    decision.decided_at.isoformat(),
                ),
            )
            sequence = cursor.lastrowid
        return decision.model_copy(update={"sequence": sequence})

    def trail(self, engagement_id: str, voucher_id: str | None = None) -> list[Decision]:
        """The full history, oldest first. This is the audit trail."""
        query = "SELECT * FROM decisions WHERE engagement_id = ?"
        params: list[object] = [engagement_id]
        if voucher_id is not None:
            query += " AND voucher_id = ?"
            params.append(voucher_id)
        query += " ORDER BY sequence"

        with self._connect() as connection, closing(connection.execute(query, params)) as cursor:
            return [_decision_from(row) for row in cursor.fetchall()]

    def current(self, engagement_id: str) -> dict[str, Decision]:
        """Where each voucher stands now: the latest decision on each."""
        latest: dict[str, Decision] = {}
        for decision in self.trail(engagement_id):
            latest[decision.voucher_id] = decision
        return latest

    def counts(self, engagement_id: str) -> dict[ReviewAction, int]:
        """How many vouchers sit in each state. Drives the progress display."""
        tally = dict.fromkeys(ReviewAction, 0)
        for decision in self.current(engagement_id).values():
            tally[decision.action] += 1
        return tally


def _engagement_from(row: sqlite3.Row) -> Engagement:
    return Engagement(
        id=row["id"],
        name=row["name"],
        entity_id=row["entity_id"],
        fiscal_year=row["fiscal_year"],
        source_name=row["source_name"],
        content_sha256=row["content_sha256"],
        voucher_count=row["voucher_count"],
        opened_at=datetime.fromisoformat(row["opened_at"]),
    )


def _decision_from(row: sqlite3.Row) -> Decision:
    return Decision(
        engagement_id=row["engagement_id"],
        voucher_id=row["voucher_id"],
        action=ReviewAction(row["action"]),
        reviewer=row["reviewer"],
        note=row["note"],
        adjusted_band=row["adjusted_band"],
        decided_at=datetime.fromisoformat(row["decided_at"]).replace(tzinfo=UTC)
        if datetime.fromisoformat(row["decided_at"]).tzinfo is None
        else datetime.fromisoformat(row["decided_at"]),
        sequence=row["sequence"],
    )
