"""Measuring explanation quality, whoever wrote it.

Five things a reviewer actually cares about, measured the same way for the
deterministic text and for anything a model produces, so the comparison is fair:

* **factual consistency** — proportion of the numbers in the text that the
  finding supports. An invented figure is the most dangerous error, because it
  looks exactly like a real one.
* **evidence coverage** — how many of the concerns actually get mentioned. Prose
  that quietly drops half the findings is worse than a list.
* **unsupported claims** — guard violations, counted rather than described.
* **readability** — words per sentence and total length. A CA reading fifty of
  these wants short ones.
* **latency** — seconds. On an 8 GB machine this is not a detail.

Deliberately dependency-free: readability is sentence length, not a proprietary
index, so nothing here needs a paid or heavyweight package.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass

import pandas as pd

from caguard.detect.types import SignalKind
from caguard.explain.guard import check_grounding
from caguard.explain.provider import ExplanationProvider
from caguard.explain.service import Explanation, ExplanationService, Source
from caguard.review.finding import Finding

_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_SENTENCE = re.compile(r"[.!?]+(?:\s|$)")

#: Words that indicate a concern was actually mentioned, whatever wording the
#: writer chose. Kept loose on purpose — a model paraphrases, and demanding an
#: exact phrase would measure obedience rather than coverage.
_CONCERN_WORDS: dict[SignalKind, tuple[str, ...]] = {
    SignalKind.MISSING_EVIDENCE: ("document", "supporting", "evidence", "unsupported"),
    SignalKind.DUPLICATE_ENTRY: ("duplicate", "twice", "same amount", "again"),
    SignalKind.ROUND_AMOUNT: ("round", "exact"),
    SignalKind.OFF_HOURS_POSTING: ("hours", "night", "outside", "working day"),
    SignalKind.WEEKEND_POSTING: ("sunday", "weekend", "office is closed"),
    SignalKind.PERIOD_END_CONCENTRATION: ("year end", "year-end", "31", "march"),
    SignalKind.RARE_ACCOUNT_PAIR: ("account", "combination", "pairing", "rare"),
    SignalKind.THRESHOLD_ADJACENT: ("limit", "approval", "threshold", "below"),
    SignalKind.UNUSUAL_PREPARER_ACCOUNT: ("posted by", "preparer", "handled", "normally"),
    SignalKind.POST_CLOSE_ENTRY: ("closed", "after", "later", "lag"),
    SignalKind.AMOUNT_OUTLIER: ("unusual", "deviation", "typical", "larger"),
    SignalKind.ML_ANOMALY: ("statistically", "unusual", "model"),
}


@dataclass(frozen=True)
class Quality:
    """How good one explanation is."""

    voucher_id: str
    source: str
    provider: str
    factual_consistency: float
    evidence_coverage: float
    unsupported_claims: int
    words: int
    words_per_sentence: float
    latency_seconds: float

    def row(self) -> dict[str, object]:
        return {
            "voucher": self.voucher_id,
            "source": self.source,
            "provider": self.provider,
            "factual_consistency": round(self.factual_consistency, 3),
            "evidence_coverage": round(self.evidence_coverage, 3),
            "unsupported_claims": self.unsupported_claims,
            "words": self.words,
            "words_per_sentence": round(self.words_per_sentence, 1),
            "latency_seconds": round(self.latency_seconds, 3),
        }


def assess(finding: Finding, explanation: Explanation) -> Quality:
    """Score one explanation against the finding it was supposed to render."""
    facts = finding.structured_facts()
    text = explanation.text
    guard = check_grounding(text, facts)

    numbers = _NUMBER.findall(text)
    consistency = 1.0 - len(guard.unsupported_numbers) / len(numbers) if numbers else 1.0

    lowered = text.lower()
    covered = sum(
        any(word in lowered for word in _CONCERN_WORDS.get(kind, ())) for kind in finding.kinds
    )
    coverage = covered / len(finding.kinds) if finding.kinds else 0.0

    words = len(text.split())
    sentences = max(len([s for s in _SENTENCE.split(text) if s.strip()]), 1)

    return Quality(
        voucher_id=finding.voucher_id,
        source=explanation.source.value,
        provider=explanation.provider,
        factual_consistency=max(0.0, consistency),
        evidence_coverage=coverage,
        unsupported_claims=len(guard.unsupported_numbers) + len(guard.forbidden_phrases),
        words=words,
        words_per_sentence=words / sentences,
        latency_seconds=explanation.latency_seconds,
    )


def compare_providers(
    findings: list[Finding],
    providers: dict[str, ExplanationProvider | None],
    *,
    timeout: float = 60.0,
) -> pd.DataFrame:
    """Run the same findings through each provider and score every explanation."""
    rows: list[dict[str, object]] = []
    for label, provider in providers.items():
        service = ExplanationService(provider, timeout=timeout)
        for finding in findings:
            explanation = service.explain(finding)
            row = assess(finding, explanation).row()
            row["variant"] = label
            rows.append(row)
    return pd.DataFrame(rows)


def summarise(frame: pd.DataFrame) -> pd.DataFrame:
    """Mean scores per variant, plus how often the model's text was actually used."""
    numeric = [
        "factual_consistency",
        "evidence_coverage",
        "unsupported_claims",
        "words",
        "words_per_sentence",
        "latency_seconds",
    ]
    grouped = frame.groupby("variant", sort=False)
    summary = pd.DataFrame(grouped[numeric].mean()).round(3)
    used = pd.Series(
        {
            str(name): round(float((group.source == Source.MODEL.value).mean()), 3)
            for name, group in grouped
        }
    )
    summary.insert(0, "model_text_used", used)
    return summary


def readability_note(words_per_sentence: float) -> str:
    """A plain reading of the sentence-length number."""
    if words_per_sentence <= 18:
        return "easy"
    if words_per_sentence <= 25:
        return "fair"
    return "heavy"


def median_latency(frame: pd.DataFrame, variant: str) -> float:
    values = frame.loc[frame.variant == variant, "latency_seconds"]
    return float(statistics.median(values)) if len(values) else 0.0
