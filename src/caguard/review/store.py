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

import secrets
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from caguard.review.decisions import Decision, ReviewAction
from caguard.review.engagement import Engagement

SCHEMA_VERSION = 2

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

#: Applied in order to bring an older file up to SCHEMA_VERSION. Each entry is
#: the script that moves a file *to* that version. Never edit one once shipped:
#: add the next number instead.
_MIGRATIONS: dict[int, str] = {
    # v2: the uploaded files themselves (D-054). The bytes live in the source
    # vault; this table records what each one was and who brought it in.
    2: """
CREATE TABLE IF NOT EXISTS source_files (
    id              TEXT PRIMARY KEY,
    engagement_id   TEXT NOT NULL REFERENCES engagements(id),
    filename        TEXT NOT NULL,
    suffix          TEXT NOT NULL,
    size_bytes      INTEGER NOT NULL,
    sha256          TEXT NOT NULL,
    uploaded_at     TEXT NOT NULL,
    uploaded_by     TEXT NOT NULL,
    rows_read       INTEGER NOT NULL,
    rows_used       INTEGER NOT NULL,
    deleted_at      TEXT,
    deleted_by      TEXT
);

CREATE INDEX IF NOT EXISTS source_files_by_engagement
    ON source_files (engagement_id, uploaded_at);
""",
}


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
        """Create or upgrade the schema. Idempotent by design.

        A fresh file starts at version 1 and climbs through the same migrations
        an existing one does, so there is one path to test, not two. A file
        from a *newer* build is refused rather than guessed at.
        """
        with self._connect() as connection:
            connection.executescript(_SCHEMA)
            row = connection.execute("SELECT version FROM schema_version").fetchone()
            if row is None:
                connection.execute("INSERT INTO schema_version (version) VALUES (1)")
                version = 1
            else:
                version = int(row["version"])

            if version > SCHEMA_VERSION:
                raise RuntimeError(
                    f"{self.path} was written by schema version {version}, "
                    f"but this build expects {SCHEMA_VERSION}. Refusing to guess."
                )
            for target in range(version + 1, SCHEMA_VERSION + 1):
                # executescript commits as it goes, so each step records its
                # version straight after its own DDL.
                connection.executescript(_MIGRATIONS[target])
                connection.execute("UPDATE schema_version SET version = ?", (target,))

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

    # --- source files --------------------------------------------------------

    def add_source(self, source: SourceFile) -> SourceFile:
        """Record an uploaded file against its engagement.

        The same bytes uploaded again to the same engagement are recorded once:
        a reviewer re-opening a ledger should not see it listed twice.
        """
        for existing in self.sources(source.engagement_id):
            if existing.sha256 == source.sha256:
                return existing
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO source_files
                   (id, engagement_id, filename, suffix, size_bytes, sha256,
                    uploaded_at, uploaded_by, rows_read, rows_used)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    source.id,
                    source.engagement_id,
                    source.filename,
                    source.suffix,
                    source.size_bytes,
                    source.sha256,
                    source.uploaded_at.isoformat(),
                    source.uploaded_by,
                    source.rows_read,
                    source.rows_used,
                ),
            )
        return source

    def sources(self, engagement_id: str, *, include_deleted: bool = False) -> list[SourceFile]:
        """An engagement's files, most recent first."""
        query = "SELECT * FROM source_files WHERE engagement_id = ?"
        if not include_deleted:
            query += " AND deleted_at IS NULL"
        query += " ORDER BY uploaded_at DESC"
        with (
            self._connect() as connection,
            closing(connection.execute(query, (engagement_id,))) as cursor,
        ):
            return [_source_from(row) for row in cursor.fetchall()]

    def source(self, source_id: str) -> SourceFile | None:
        with (
            self._connect() as connection,
            closing(
                connection.execute("SELECT * FROM source_files WHERE id = ?", (source_id,))
            ) as cursor,
        ):
            row = cursor.fetchone()
        return _source_from(row) if row else None

    def mark_source_deleted(self, source_id: str, deleted_by: str) -> SourceFile | None:
        """Record that a file's bytes were deleted, and by whom.

        The row stays: the report and the trail still need to say which file a
        decision was made on, after the file itself is gone.
        """
        with self._connect() as connection:
            connection.execute(
                """UPDATE source_files SET deleted_at = ?, deleted_by = ?
                   WHERE id = ? AND deleted_at IS NULL""",
                (datetime.now(UTC).isoformat(), deleted_by, source_id),
            )
        return self.source(source_id)

    def sha_still_referenced(self, sha256: str) -> bool:
        """Whether any live record still points at these bytes."""
        with (
            self._connect() as connection,
            closing(
                connection.execute(
                    "SELECT 1 FROM source_files WHERE sha256 = ? AND deleted_at IS NULL LIMIT 1",
                    (sha256,),
                )
            ) as cursor,
        ):
            return cursor.fetchone() is not None

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


class SourceFile(BaseModel):
    """One uploaded file, as recorded. The bytes themselves live in the vault."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(default_factory=lambda: secrets.token_hex(8))
    engagement_id: str
    #: As the user named it. Shown, never used to build a path.
    filename: str
    suffix: str
    size_bytes: int = Field(ge=0)
    sha256: str = Field(min_length=64, max_length=64)
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    uploaded_by: str
    rows_read: int = Field(ge=0)
    rows_used: int = Field(ge=0)
    deleted_at: datetime | None = None
    deleted_by: str | None = None

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


def _source_from(row: sqlite3.Row) -> SourceFile:
    return SourceFile(
        id=row["id"],
        engagement_id=row["engagement_id"],
        filename=row["filename"],
        suffix=row["suffix"],
        size_bytes=row["size_bytes"],
        sha256=row["sha256"],
        uploaded_at=_utc(row["uploaded_at"]),
        uploaded_by=row["uploaded_by"],
        rows_read=row["rows_read"],
        rows_used=row["rows_used"],
        deleted_at=_utc(row["deleted_at"]) if row["deleted_at"] else None,
        deleted_by=row["deleted_by"],
    )


def _utc(text: str) -> datetime:
    value = datetime.fromisoformat(text)
    return value if value.tzinfo else value.replace(tzinfo=UTC)


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
