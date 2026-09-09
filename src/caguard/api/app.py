"""The FastAPI application behind the review workspace.

Local by design. It binds to loopback, stores decisions in a local SQLite file,
and needs no account, no key and no network. The privacy claim this project
makes is that a client's ledger stays on the machine, and an HTTP server is
exactly where that claim is easiest to break by accident — so the bind address
is checked rather than trusted.

Findings are computed, not stored. A ledger is analysed once and the result is
held in memory for the life of the process, keyed by the ledger's content hash:
re-running the same book at the same version reproduces the same findings, so
there is nothing to persist and nothing that can drift.
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse

from caguard.api.auth_routes import build_auth_router, current_user_dependency
from caguard.api.models import (
    DecisionIn,
    DecisionOut,
    EngagementOut,
    ExplanationOut,
    FindingOut,
    IntakeReportOut,
    QueueOut,
)
from caguard.auth import UserStore
from caguard.auth.sessions import load_or_create_key
from caguard.auth.users import User
from caguard.detect.types import DetectorConfig
from caguard.explain.ollama import OllamaProvider
from caguard.explain.service import ExplanationService
from caguard.intake.normalise import NormalisationError, NormalisationReport, normalise
from caguard.intake.readers import SUPPORTED_SUFFIXES, IntakeError, read_table, safe_suffix
from caguard.review.decisions import Decision, ReviewAction
from caguard.review.engagement import Engagement, open_engagement
from caguard.review.finding import Finding, RiskBand
from caguard.review.fusion import build_findings
from caguard.review.report import build_rows, to_csv, to_html
from caguard.review.store import ReviewStore

MAX_UPLOAD_BYTES = 200 * 1024 * 1024


@dataclass
class Analysis:
    """One analysed ledger, held for the life of the process."""

    engagement: Engagement
    lines: pd.DataFrame
    findings: list[Finding]
    intake: NormalisationReport | None = None

    @property
    def by_voucher(self) -> dict[str, Finding]:
        return {finding.voucher_id: finding for finding in self.findings}


@dataclass
class Workspace:
    """Shared state: the store on disk, and analyses held in memory."""

    store: ReviewStore
    config: DetectorConfig = field(default_factory=DetectorConfig)
    model: str = "none"
    analyses: dict[str, Analysis] = field(default_factory=dict)

    def explanation_service(self) -> ExplanationService:
        """A service for the configured model, or the deterministic path.

        Built per request rather than held: the model may be started or stopped
        while the workspace is open, and a reviewer should not have to restart
        the application because Ollama came up.
        """
        if self.model == "none":
            return ExplanationService()
        return ExplanationService(OllamaProvider(model=self.model), timeout=60.0)

    def model_available(self) -> bool:
        if self.model == "none":
            return False
        return OllamaProvider(model=self.model).available()

    def analyse(
        self,
        lines: pd.DataFrame,
        source: str,
        intake: NormalisationReport | None = None,
    ) -> Analysis:
        engagement = self.store.open_engagement(open_engagement(lines, source=source))
        cached = self.analyses.get(engagement.id)
        if cached is not None:
            return cached
        analysis = Analysis(engagement, lines, build_findings(lines, self.config), intake=intake)
        self.analyses[engagement.id] = analysis
        return analysis

    def require(self, engagement_id: str) -> Analysis:
        analysis = self.analyses.get(engagement_id)
        if analysis is None:
            raise HTTPException(
                404,
                f"Engagement {engagement_id!r} is not loaded. Upload its ledger again — "
                "findings are recomputed rather than stored, so nothing is lost.",
            )
        return analysis


def create_app(
    store_path: Path | str = "data/review.db",
    *,
    config: DetectorConfig | None = None,
    model: str = "none",
) -> FastAPI:
    """Build the application. Nothing is analysed until a ledger is uploaded."""
    workspace = Workspace(
        store=ReviewStore(store_path), config=config or DetectorConfig(), model=model
    )
    data_dir = Path(store_path).parent
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

    @app.get("/api/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "model": workspace.model,
            "model_available": workspace.model_available(),
            "engagements_loaded": len(workspace.analyses),
            # Set on a hosted deployment so the interface can say plainly that it
            # is a demonstration on synthetic data. The privacy claim belongs to
            # the self-hosted path, and wording that blurs the two would mislead
            # a CA about where their client's ledger sits (D-005).
            "demo_mode": os.environ.get("CAGUARD_DEMO", "").strip().lower() in {"1", "true", "yes"},
        }

    @app.get("/api/engagements", response_model=list[EngagementOut])
    def list_engagements(user: User = signed_in) -> list[EngagementOut]:
        return [EngagementOut.build(e) for e in workspace.store.engagements()]

    @app.post("/api/engagements", response_model=QueueOut)
    async def upload(file: UploadFile, user: User = signed_in) -> QueueOut:
        """Upload a ledger, analyse it, and return the review queue."""
        payload = await file.read()
        if len(payload) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"File is larger than {MAX_UPLOAD_BYTES // 1024 // 1024} MB")

        # Never build a path from an uploaded filename: only a suffix we
        # recognise is carried across.
        suffix = safe_suffix(file.filename)
        if not suffix:
            raise HTTPException(
                400,
                f"Unsupported file type. CA-Guard reads {', '.join(sorted(SUPPORTED_SUFFIXES))}.",
            )
        temp = Path(workspace.store.path).parent / f"_upload{suffix}"
        temp.write_bytes(payload)
        try:
            raw = read_table(temp)
        except IntakeError as exc:
            raise HTTPException(400, str(exc)) from exc
        finally:
            temp.unlink(missing_ok=True)

        # A real ledger does not arrive in our schema. Map it, derive what can be
        # derived, and say plainly what the file did not contain.
        try:
            normalised = normalise(raw)
        except NormalisationError as exc:
            raise HTTPException(400, str(exc)) from exc

        try:
            analysis = workspace.analyse(
                normalised.lines,
                source=file.filename or "uploaded ledger",
                intake=normalised.report,
            )
        except Exception as exc:
            raise HTTPException(
                400,
                "CA-Guard could not analyse this file. It was read and its columns "
                f"were recognised, but the analysis failed: {exc}",
            ) from exc

        return _queue(workspace, analysis)

    @app.get("/api/engagements/{engagement_id}/queue", response_model=QueueOut)
    def queue(engagement_id: str, user: User = signed_in) -> QueueOut:
        return _queue(workspace, workspace.require(engagement_id))

    @app.get(
        "/api/engagements/{engagement_id}/findings/{voucher_id}",
        response_model=FindingOut,
    )
    def finding(engagement_id: str, voucher_id: str, user: User = signed_in) -> FindingOut:
        analysis = workspace.require(engagement_id)
        found = analysis.by_voucher.get(voucher_id)
        if found is None:
            raise HTTPException(404, f"No finding for voucher {voucher_id!r}")
        current = workspace.store.current(engagement_id).get(voucher_id)
        return FindingOut.build(found, current)

    @app.get(
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

    @app.post("/api/engagements/{engagement_id}/decisions", response_model=DecisionOut)
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

    @app.get("/api/engagements/{engagement_id}/trail", response_model=list[DecisionOut])
    def trail(
        engagement_id: str, voucher_id: str | None = None, user: User = signed_in
    ) -> list[DecisionOut]:
        """The full audit trail, oldest first. Nothing is ever removed from it."""
        return [DecisionOut.build(d) for d in workspace.store.trail(engagement_id, voucher_id)]

    @app.get("/api/engagements/{engagement_id}/report.csv")
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

    @app.get("/api/engagements/{engagement_id}/report.html")
    def report_html(engagement_id: str, user: User = signed_in) -> HTMLResponse:
        analysis = workspace.require(engagement_id)
        rows = build_rows(analysis.findings, workspace.store.current(engagement_id))
        return HTMLResponse(to_html(analysis.engagement, rows))

    return app


def _queue(workspace: Workspace, analysis: Analysis) -> QueueOut:
    decisions = workspace.store.current(analysis.engagement.id)
    findings = [FindingOut.build(f, decisions.get(f.voucher_id)) for f in analysis.findings]

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
