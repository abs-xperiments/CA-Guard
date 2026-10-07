"""The FastAPI application behind the review workspace.

Local by design. It binds to loopback, stores decisions in a local SQLite file,
and needs no account, no key and no network. The privacy claim this project
makes is that a client's ledger stays on the machine, and an HTTP server is
exactly where that claim is easiest to break by accident — so the bind address
is checked rather than trusted.

Findings are computed, not stored: re-running the same book at the same version
reproduces them exactly, so there is nothing that can drift. The uploaded file
itself *is* kept (D-054), byte for byte, so an engagement re-opens from its own
original after a restart — see `caguard.api.workspace`.
"""

from __future__ import annotations

import io
import logging
import os
import secrets
import tempfile
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, FastAPI, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, PlainTextResponse

from caguard.api.auth_routes import build_auth_router, current_user_dependency
from caguard.api.models import (
    DecisionIn,
    DecisionOut,
    EngagementOut,
    EngagementSummaryOut,
    ExplanationOut,
    FindingOut,
    IntakeReportOut,
    QueueOut,
    RenameIn,
)
from caguard.api.source_routes import build_source_router
from caguard.api.workspace import Analysis, Workspace
from caguard.auth import UserStore
from caguard.auth.sessions import load_or_create_key
from caguard.auth.users import User
from caguard.detect.types import DetectorConfig
from caguard.explain.card import build_card
from caguard.intake.normalise import normalise
from caguard.intake.readers import (
    MAX_UPLOAD_BYTES,
    SUPPORTED_SUFFIXES,
    read_table,
    safe_suffix,
)
from caguard.review.decisions import Decision, ReviewAction
from caguard.review.finding import RiskBand
from caguard.review.report import build_rows, to_csv, to_html
from caguard.review.sources import SourceVault
from caguard.review.store import ReviewStore

#: Uploads are copied to disk in chunks of this size, so a large ledger is never
#: held in memory twice and an oversized one is refused part-way through.
UPLOAD_CHUNK_BYTES = 1024 * 1024

logger = logging.getLogger("caguard.api")


def create_app(
    store_path: Path | str = "data/review.db",
    *,
    config: DetectorConfig | None = None,
    model: str = "none",
) -> FastAPI:
    """Build the application. Nothing is analysed until a ledger is uploaded."""
    data_dir = Path(store_path).parent
    demo = demo_mode()
    workspace = Workspace(
        isolate_users=demo,
        store=ReviewStore(store_path),
        vault=SourceVault(data_dir / "sources"),
        config=config or DetectorConfig(),
        model=model,
    )
    users = UserStore(store_path)
    signing_key = load_or_create_key(data_dir)

    app = FastAPI(
        title="CA-Guard",
        summary="Private review workspace for Indian Chartered Accountants",
        version="0.1.0",
    )
    app.state.workspace = workspace
    app.state.users = users
    app.include_router(build_auth_router(users, data_dir, signing_key))

    # Every route below touches a client's ledger, so every one of them requires
    # a signed-in user. Applied as a dependency rather than remembered per route,
    # because a route someone forgets to protect is the one that leaks.
    signed_in = Depends(current_user_dependency(users, signing_key))

    def can_open(engagement_id: str, user: User = signed_in) -> None:
        # The same answer for "not yours" and "does not exist": on the demo, an
        # engagement id must not confirm that someone else's work exists.
        if not workspace.can_see(engagement_id, user.id):
            raise HTTPException(404, "There is no such engagement.")

    # Every route under one engagement goes through this router, so the access
    # check is applied once, not remembered route by route.
    scoped = APIRouter(dependencies=[Depends(can_open)])

    @app.get("/api/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "model": workspace.model,
            "model_available": workspace.model_available(),
            # Set on a hosted deployment so the interface can say plainly that it
            # is a demonstration on synthetic data. The privacy claim belongs to
            # the self-hosted path, and wording that blurs the two would mislead
            # a CA about where their client's ledger sits (D-005).
            "demo_mode": demo,
        }

    @app.get("/api/engagements", response_model=list[EngagementSummaryOut])
    def list_engagements(user: User = signed_in) -> list[EngagementSummaryOut]:
        owner = user.id if workspace.isolate_users else None
        return [EngagementSummaryOut.build(s) for s in workspace.store.summaries(owner)]

    @scoped.patch("/api/engagements/{engagement_id}", response_model=EngagementOut)
    def rename(engagement_id: str, body: RenameIn, user: User = signed_in) -> EngagementOut:
        """Give an engagement a name the firm recognises, e.g. "Sharma Traders — FY25"."""
        if workspace.store.engagement(engagement_id) is None:
            raise HTTPException(404, "There is no such engagement.")
        workspace.store.rename(engagement_id, body.name)
        renamed = workspace.store.engagement(engagement_id)
        assert renamed is not None
        analysis = workspace.analyses.get(engagement_id)
        if analysis is not None:
            analysis.engagement = renamed
        return EngagementOut.build(renamed)

    @app.post("/api/engagements", response_model=QueueOut)
    async def upload(file: UploadFile, user: User = signed_in) -> QueueOut:
        """Upload a ledger, analyse it, and return the review queue."""
        display_name = Path(file.filename or "uploaded ledger").name or "uploaded ledger"

        # Never build a path from an uploaded filename: only a suffix we
        # recognise is carried across.
        suffix = safe_suffix(file.filename)
        if not suffix:
            raise HTTPException(
                400,
                f"{display_name} is not a file type CA-Guard reads. Upload "
                f"{', '.join(sorted(SUPPORTED_SUFFIXES))}. Nothing was saved.",
            )

        temp = await _receive(file, Path(workspace.store.path).parent, suffix, display_name)
        try:
            # Parsing and analysis are CPU-bound and can take seconds on a full
            # year's ledger. Run on the event loop, they froze the whole server
            # for every user until they finished (measured: 12 s for a health
            # check during a 13.5 s analysis).
            analysis = await run_in_threadpool(_ingest, workspace, temp, suffix, display_name, user)
        finally:
            temp.unlink(missing_ok=True)
        return _queue(workspace, analysis)

    @scoped.get("/api/engagements/{engagement_id}/queue", response_model=QueueOut)
    def queue(engagement_id: str, user: User = signed_in) -> QueueOut:
        return _queue(workspace, workspace.require(engagement_id))

    @scoped.get(
        "/api/engagements/{engagement_id}/findings/{voucher_id}",
        response_model=FindingOut,
    )
    def finding(engagement_id: str, voucher_id: str, user: User = signed_in) -> FindingOut:
        analysis = workspace.require(engagement_id)
        found = analysis.by_voucher.get(voucher_id)
        if found is None:
            raise HTTPException(404, f"No finding for voucher {voucher_id!r}")
        current = workspace.store.current(engagement_id).get(voucher_id)
        card = (
            build_card(
                found,
                analysis.context,
                account_names=analysis.account_names,
                not_in_file=analysis.not_in_file,
                flagged=analysis.flagged,
                config=workspace.config,
            )
            if analysis.context is not None
            else None
        )
        return FindingOut.build(
            found,
            current,
            lines=analysis.lines_for(voucher_id),
            source=analysis.source,
            card=card,
        )

    @scoped.get(
        "/api/engagements/{engagement_id}/findings/{voucher_id}/explanation",
        response_model=ExplanationOut,
    )
    def explanation(engagement_id: str, voucher_id: str, user: User = signed_in) -> ExplanationOut:
        """Plain-language explanation. Always returns text, model or not."""
        analysis = workspace.require(engagement_id)
        found = analysis.by_voucher.get(voucher_id)
        if found is None:
            raise HTTPException(404, f"No finding for voucher {voucher_id!r}")

        result = workspace.explanation_service().explain(found)
        return ExplanationOut(
            voucher_id=result.voucher_id,
            text=result.text,
            source=result.source.value,
            provider=result.provider,
            latency_seconds=result.latency_seconds,
            provenance=result.provenance(),
        )

    @scoped.post("/api/engagements/{engagement_id}/decisions", response_model=DecisionOut)
    def decide(engagement_id: str, body: DecisionIn, user: User = signed_in) -> DecisionOut:
        analysis = workspace.require(engagement_id)
        if body.voucher_id not in analysis.by_voucher:
            raise HTTPException(404, f"No finding for voucher {body.voucher_id!r}")
        try:
            decision = Decision(
                engagement_id=engagement_id,
                voucher_id=body.voucher_id,
                action=body.action,
                # From the session, never the request body: an audit trail
                # anyone can sign with anyone's name is not an audit trail.
                reviewer=user.display_name,
                note=body.note,
                adjusted_band=body.adjusted_band,
            )
        except ValueError as exc:
            # A rejection without a reason. Surfaced as a 422 with the reason why.
            raise HTTPException(422, str(exc)) from exc
        return DecisionOut.build(workspace.store.record(decision))

    @scoped.get("/api/engagements/{engagement_id}/trail", response_model=list[DecisionOut])
    def trail(
        engagement_id: str, voucher_id: str | None = None, user: User = signed_in
    ) -> list[DecisionOut]:
        """The full audit trail, oldest first. Nothing is ever removed from it."""
        return [DecisionOut.build(d) for d in workspace.store.trail(engagement_id, voucher_id)]

    @scoped.get("/api/engagements/{engagement_id}/report.csv")
    def report_csv(engagement_id: str, user: User = signed_in) -> PlainTextResponse:
        analysis = workspace.require(engagement_id)
        rows = build_rows(analysis.findings, workspace.store.current(engagement_id))
        return PlainTextResponse(
            to_csv(rows),
            media_type="text/csv",
            headers={
                "Content-Disposition": (f'attachment; filename="ca-guard-{engagement_id}.csv"')
            },
        )

    @scoped.get("/api/engagements/{engagement_id}/report.html")
    def report_html(engagement_id: str, user: User = signed_in) -> HTMLResponse:
        analysis = workspace.require(engagement_id)
        rows = build_rows(analysis.findings, workspace.store.current(engagement_id))
        return HTMLResponse(
            to_html(
                analysis.engagement,
                rows,
                generated_by=user.display_name,
                sources=workspace.store.sources(engagement_id, include_deleted=True),
            ),
            headers={"Cache-Control": "no-store"},
        )

    app.include_router(scoped)
    app.include_router(build_source_router(workspace, signed_in), dependencies=[Depends(can_open)])
    return app


def _text_or_none(value: object) -> str | None:
    return value.strip() or None if isinstance(value, str) else None


def demo_mode() -> bool:
    """Set on a hosted deployment (D-005, D-052): banner on, users isolated."""
    return os.environ.get("CAGUARD_DEMO", "").strip().lower() in {"1", "true", "yes"}


async def _receive(file: UploadFile, directory: Path, suffix: str, display_name: str) -> Path:
    """Copy an upload to a private temporary file, refusing it once it is too big.

    The name is unique per request: a shared name meant two simultaneous
    uploads could read each other's ledger.
    """
    directory.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(  # noqa: SIM115 - closed below, unlinked by caller
        dir=directory, prefix="upload-", suffix=suffix, delete=False
    )
    path = Path(handle.name)
    received = 0
    try:
        with handle:
            while chunk := await file.read(UPLOAD_CHUNK_BYTES):
                received += len(chunk)
                if received > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        413,
                        f"{display_name} is larger than "
                        f"{MAX_UPLOAD_BYTES // 1024 // 1024} MB. Nothing was saved.",
                    )
                handle.write(chunk)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def _ingest(
    workspace: Workspace, path: Path, suffix: str, display_name: str, user: User
) -> Analysis:
    """Analyse and keep one upload, turning any failure into a message to act on.

    Expected problems (an unreadable file, missing columns) arrive as
    HTTPExceptions with their own wording. Anything else is logged with an
    error id the reviewer can quote, and the message says what did not happen
    rather than showing an internal exception.
    """
    try:
        return workspace.ingest(
            path, suffix, display_name, uploaded_by=user.display_name, owner_id=user.id
        )
    except HTTPException:
        raise
    except Exception as exc:
        error_id = secrets.token_hex(4)
        # Metadata only. Not the traceback: exception text from the data layer can
        # quote cell values, and a log file must never become a copy of a ledger.
        # The failure reproduces locally with `caguard review <file>`.
        logger.error("analysis failed error_id=%s error_type=%s", error_id, type(exc).__name__)
        raise HTTPException(
            500,
            f"{display_name} was read and its columns were recognised, but the analysis "
            f"could not be completed. Nothing was saved. Error reference: {error_id}.",
        ) from exc


def _queue(workspace: Workspace, analysis: Analysis) -> QueueOut:
    decisions = workspace.store.current(analysis.engagement.id)
    vouchers = analysis.context.vouchers if analysis.context is not None else None
    findings = []
    for f in analysis.findings:
        accounts: list[str] = []
        narration: str | None = None
        prepared_by: str | None = None
        if vouchers is not None and f.voucher_id in vouchers.index:
            accounts = [str(name) for name in vouchers.at[f.voucher_id, "account_names"]]
            narration = _text_or_none(vouchers.at[f.voucher_id, "narration"])
            prepared_by = _text_or_none(vouchers.at[f.voucher_id, "created_by"])
        findings.append(
            FindingOut.build(
                f,
                decisions.get(f.voucher_id),
                accounts=accounts,
                narration=narration,
                prepared_by=prepared_by,
                signal_evidence=False,
            )
        )

    bands = {band.value: sum(1 for f in analysis.findings if f.band is band) for band in RiskBand}
    states = {
        action.value: sum(1 for d in decisions.values() if d.action is action)
        for action in ReviewAction
    }
    states["not yet reviewed"] = len(findings) - sum(states.values())

    intake = analysis.intake
    return QueueOut(
        intake=(
            IntakeReportOut(
                summary=intake.summary(),
                mapped=intake.mapped,
                derived=intake.derived,
                not_in_file=intake.defaulted,
                ignored=intake.ignored,
                notes=intake.notes,
                rows_read=intake.rows_in,
                rows_used=intake.rows_out,
            )
            if intake is not None
            else None
        ),
        engagement=EngagementOut.build(analysis.engagement),
        findings=findings,
        total_vouchers=analysis.engagement.voucher_count,
        flagged=len(findings),
        bands=bands,
        states=states,
        model_available=workspace.model_available(),
    )


def load_ledger(path: Path | str) -> pd.DataFrame:
    """Read a ledger from disk, normalised and ready for the pipeline."""
    return normalise(read_table(Path(path))).lines


def frame_from_csv(text: str) -> pd.DataFrame:
    return pd.read_csv(io.StringIO(text))
