"""Orchestration: try the model, check it, fall back without drama.

The service is where the phase's one rule is enforced in code. It takes a
Finding that is already complete — priority, band, signals, evidence — asks a
provider to render it, checks the result against the same facts, and returns
whichever text is trustworthy. The Finding itself is never touched.

Every outcome is a success from the product's point of view. No model, a broken
model, a slow model, a model that invented a number: each of those returns a
written explanation, and the queue is identical either way.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum

from caguard.explain.deterministic import DISCLAIMER, explain_deterministically
from caguard.explain.guard import GuardResult, check_grounding
from caguard.explain.prompt import build_messages
from caguard.explain.provider import (
    ExplanationProvider,
    NullProvider,
    ProviderError,
)
from caguard.review.finding import Finding

#: How long a local model gets before the deterministic text is used instead. A
#: reviewer waiting on prose has already read the finding.
DEFAULT_TIMEOUT = 30.0


class Source(StrEnum):
    """Where the text a reviewer is reading actually came from."""

    DETERMINISTIC = "deterministic"
    MODEL = "model"


@dataclass(frozen=True)
class Explanation:
    """The text shown for a finding, and an honest record of its provenance."""

    voucher_id: str
    text: str
    source: Source
    provider: str
    latency_seconds: float
    guard: GuardResult | None = None
    fallback_reason: str | None = None

    @property
    def was_generated(self) -> bool:
        return self.source is Source.MODEL

    def provenance(self) -> str:
        """One line a reviewer can read to know what wrote this."""
        if self.was_generated:
            return f"Written by {self.provider} from the recorded facts, checked before display."
        if self.fallback_reason:
            return f"Written by CA-Guard ({self.fallback_reason})."
        return "Written by CA-Guard."


class ExplanationService:
    """Turns findings into readable text, with the deterministic path always available."""

    def __init__(
        self,
        provider: ExplanationProvider | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.provider: ExplanationProvider = provider or NullProvider()
        self.timeout = timeout

    def explain(self, finding: Finding) -> Explanation:
        """Explain one finding. Always returns text; never alters the finding."""
        facts = finding.structured_facts()
        deterministic = explain_deterministically(finding)

        if not self.provider.available():
            return self._fallback(finding, deterministic, "no local model available", elapsed=0.0)

        started = time.perf_counter()
        try:
            generated = self.provider.generate(build_messages(facts), timeout=self.timeout)
        except ProviderError as exc:
            return self._fallback(
                finding, deterministic, str(exc), elapsed=time.perf_counter() - started
            )
        elapsed = time.perf_counter() - started

        guard = check_grounding(generated, facts)
        if not guard.passed:
            # The model said something the finding does not support. It does not
            # get shown and it does not get a second attempt.
            return self._fallback(
                finding, deterministic, guard.summary(), elapsed=elapsed, guard=guard
            )

        return Explanation(
            voucher_id=finding.voucher_id,
            text=_with_disclaimer(generated),
            source=Source.MODEL,
            provider=self.provider.name,
            latency_seconds=round(elapsed, 3),
            guard=guard,
        )

    def explain_all(self, findings: list[Finding]) -> list[Explanation]:
        return [self.explain(finding) for finding in findings]

    def _fallback(
        self,
        finding: Finding,
        text: str,
        reason: str,
        *,
        elapsed: float,
        guard: GuardResult | None = None,
    ) -> Explanation:
        return Explanation(
            voucher_id=finding.voucher_id,
            text=text,
            source=Source.DETERMINISTIC,
            provider=self.provider.name,
            latency_seconds=round(elapsed, 3),
            guard=guard,
            fallback_reason=reason,
        )


def _with_disclaimer(text: str) -> str:
    """Every explanation carries the same caveat, however it was written."""
    return text.strip() if DISCLAIMER in text else f"{text.strip()}\n\n{DISCLAIMER}"
