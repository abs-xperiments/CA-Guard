"""What the API holds: analyses in memory, originals in the vault, decisions on disk.

Findings are still computed rather than stored — re-running the same book at the
same version reproduces them exactly. What changed (D-054) is that the uploaded
file itself is now kept, so an engagement the process has not seen since a
restart is re-analysed from its own original instead of asking the reviewer to
upload it again.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import pandas as pd
from fastapi import HTTPException

from caguard.detect.context import LedgerContext, build_context
from caguard.detect.types import DetectorConfig
from caguard.explain.ollama import OllamaProvider
from caguard.explain.service import ExplanationService
from caguard.intake.normalise import NormalisationError, NormalisationReport, normalise
from caguard.intake.readers import IntakeError, read_table
from caguard.review.engagement import Engagement, ledger_hash, open_engagement
from caguard.review.finding import Finding
from caguard.review.fusion import build_findings
from caguard.review.sources import SourceIntegrityError, SourceVault
from caguard.review.store import ReviewStore, SourceFile

logger = logging.getLogger("caguard.api")


@dataclass
class Analysis:
    """One analysed ledger, held for the life of the process."""

    engagement: Engagement
    lines: pd.DataFrame
    findings: list[Finding]
    intake: NormalisationReport | None = None
    #: The file as read, before normalisation — what the source preview shows.
    raw: pd.DataFrame | None = None
    #: The stored original these findings were computed from.
    source: SourceFile | None = None
    #: The per-voucher view the detectors used; the explanation card reuses it
    #: so its comparisons are the detectors' comparisons.
    context: LedgerContext | None = None

    @cached_property
    def flagged(self) -> frozenset[str]:
        return frozenset(f.voucher_id for f in self.findings)

    @cached_property
    def account_names(self) -> dict[str, str]:
        if not {"account_code", "account_name"} <= set(self.lines.columns):
            return {}
        names: dict[str, str] = {}
        pairs = self.lines[["account_code", "account_name"]].dropna()
        for code, name in pairs.itertuples(index=False):
            names.setdefault(str(code), str(name))  # first name seen wins
        return names

    @property
    def not_in_file(self) -> frozenset[str]:
        """Columns the uploaded file did not have, so cannot be judged on."""
        return frozenset(self.intake.defaulted) if self.intake else frozenset()

    @cached_property
    def by_voucher(self) -> dict[str, Finding]:
        return {finding.voucher_id: finding for finding in self.findings}

    @cached_property
    def _line_positions(self) -> dict[str, list[int]]:
        if "voucher_id" not in self.lines.columns:
            return {}
        grouped = self.lines.groupby("voucher_id", sort=False).indices
        return {str(voucher): list(positions) for voucher, positions in grouped.items()}

    def lines_for(self, voucher_id: str) -> pd.DataFrame:
        """The ledger lines behind one voucher, in their original order."""
        positions = self._line_positions.get(voucher_id, [])
        return self.lines.iloc[positions]


@dataclass
class Workspace:
    """Shared state: the store and vault on disk, and analyses held in memory."""

    store: ReviewStore
    vault: SourceVault
    config: DetectorConfig = field(default_factory=DetectorConfig)
    model: str = "none"
    analyses: dict[str, Analysis] = field(default_factory=dict)
    #: Public-demo mode: each account sees only the engagements it opened.
    isolate_users: bool = False
    _reload_lock: threading.Lock = field(default_factory=threading.Lock)

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

    # --- analysing ------------------------------------------------------------

    def analyse(
        self,
        lines: pd.DataFrame,
        source: str,
        intake: NormalisationReport | None = None,
        *,
        raw: pd.DataFrame | None = None,
        owner_id: str = "",
    ) -> Analysis:
        scope = owner_id if self.isolate_users else ""
        engagement = self.store.open_engagement(
            open_engagement(lines, source=source, scope=scope), owner_id=owner_id
        )
        cached = self.analyses.get(engagement.id)
        if cached is not None:
            return cached
        context = build_context(lines)
        analysis = Analysis(
            engagement,
            lines,
            build_findings(lines, self.config, context=context),
            intake=intake,
            raw=raw,
            context=context,
        )
        self.analyses[engagement.id] = analysis
        self._record_stats(analysis)
        return analysis

    def _record_stats(self, analysis: Analysis) -> None:
        bands = [f.band.value for f in analysis.findings]
        self.store.record_stats(
            analysis.engagement.id,
            flagged=len(bands),
            high=bands.count("high"),
            medium=bands.count("medium"),
        )

    def can_see(self, engagement_id: str, user_id: str) -> bool:
        """Whether this account may open this engagement.

        Self-hosted, every reviewer in the firm shares the workspace. On the
        public demo, only the account that opened an engagement can see it.
        """
        if not self.isolate_users:
            return True
        return self.store.owner_of(engagement_id) == user_id

    def ingest(
        self,
        path: Path,
        suffix: str,
        display_name: str,
        uploaded_by: str,
        owner_id: str = "",
    ) -> Analysis:
        """Read, analyse and keep one uploaded file. Runs in a worker thread.

        The file is kept only once the analysis has succeeded, so a file
        CA-Guard could not use is never stored.
        """
        raw = _read(path, display_name)
        normalised = _normalise(raw, display_name)
        analysis = self.analyse(
            normalised.lines,
            source=display_name,
            intake=normalised.report,
            raw=raw,
            owner_id=owner_id,
        )

        stored = self.vault.keep(path, suffix)
        source = self.store.add_source(
            SourceFile(
                engagement_id=analysis.engagement.id,
                filename=display_name,
                suffix=suffix,
                size_bytes=stored.size_bytes,
                sha256=stored.sha256,
                uploaded_by=uploaded_by,
                rows_read=normalised.report.rows_in,
                rows_used=normalised.report.rows_out,
            )
        )
        if analysis.source is None:
            analysis.source = source
        return analysis

    # --- finding an engagement again -----------------------------------------

    def require(self, engagement_id: str) -> Analysis:
        """An engagement's analysis, re-built from its stored original if need be."""
        analysis = self.analyses.get(engagement_id)
        if analysis is not None:
            return analysis

        engagement = self.store.engagement(engagement_id)
        if engagement is None:
            raise HTTPException(404, "There is no such engagement.")

        # One rebuild at a time: two tabs opening the same engagement after a
        # restart should not analyse the same ledger twice.
        with self._reload_lock:
            analysis = self.analyses.get(engagement_id)
            if analysis is None:
                analysis = self._rebuild(engagement)
                self.analyses[engagement_id] = analysis
        return analysis

    def forget(self, engagement_id: str) -> None:
        self.analyses.pop(engagement_id, None)

    def _rebuild(self, engagement: Engagement) -> Analysis:
        live = self.store.sources(engagement.id)
        if not live:
            if self.store.sources(engagement.id, include_deleted=True):
                detail = (
                    "The original file for this engagement was deleted. Upload the ledger "
                    "again to continue; the decisions already recorded are kept."
                )
            else:
                detail = (
                    "This engagement was opened before CA-Guard kept original files. Upload "
                    "the ledger once more to continue; the decisions already recorded are kept."
                )
            raise HTTPException(409, detail)

        for source in live:
            try:
                path = self.vault.verified_path(source.sha256, source.suffix)
            except FileNotFoundError:
                logger.error("stored original missing source_id=%s", source.id)
                continue
            except SourceIntegrityError:
                logger.error("stored original failed its hash check source_id=%s", source.id)
                continue

            raw = _read(path, source.filename)
            normalised = _normalise(raw, source.filename)
            if ledger_hash(normalised.lines) != engagement.content_sha256:
                # The file now reads as a different book — most likely a newer
                # build normalises it differently. Saying so beats quietly
                # showing findings the recorded decisions were not made on.
                logger.error("rebuilt ledger hash differs source_id=%s", source.id)
                continue

            context = build_context(normalised.lines)
            rebuilt = Analysis(
                engagement,
                normalised.lines,
                build_findings(normalised.lines, self.config, context=context),
                intake=normalised.report,
                raw=raw,
                source=source,
                context=context,
            )
            self._record_stats(rebuilt)
            return rebuilt

        raise HTTPException(
            409,
            "CA-Guard could not re-open this engagement from its stored original. Upload "
            "the ledger again to continue; the decisions already recorded are kept.",
        )


def _read(path: Path, display_name: str) -> pd.DataFrame:
    try:
        return read_table(path, display_name=display_name)
    except IntakeError as exc:
        raise HTTPException(400, str(exc)) from exc


def _normalise(raw: pd.DataFrame, display_name: str):
    # A real ledger does not arrive in our schema. Map it, derive what can be
    # derived, and say plainly what the file did not contain.
    try:
        return normalise(raw)
    except NormalisationError as exc:
        raise HTTPException(400, f"{display_name}: {exc}") from exc
