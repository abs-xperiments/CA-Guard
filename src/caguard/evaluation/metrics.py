"""Metrics over sets of voucher ids.

Kept generic on purpose: these functions know nothing about benchmarks, planted
anomalies or ground-truth files. They take "what we flagged" and "what was
actually there" as plain sets, which means the evaluation library itself has no
route to the generator and the ADR-0003 separation costs nothing to maintain.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Outcome:
    """The result of comparing what we flagged against what was there."""

    predicted: int
    actual: int
    hits: int

    @property
    def recall(self) -> float:
        """Of what was there, how much did we surface?"""
        return self.hits / self.actual if self.actual else 0.0

    @property
    def precision(self) -> float:
        """Of what we surfaced, how much was worth surfacing?"""
        return self.hits / self.predicted if self.predicted else 0.0

    @property
    def f1(self) -> float:
        total = self.precision + self.recall
        return 2 * self.precision * self.recall / total if total else 0.0

    def __str__(self) -> str:
        return (
            f"recall {self.recall:.0%} ({self.hits}/{self.actual}), "
            f"precision {self.precision:.0%} ({self.hits}/{self.predicted})"
        )


def score(predicted: set[str], actual: set[str]) -> Outcome:
    """Compare flagged vouchers against the vouchers that mattered."""
    return Outcome(len(predicted), len(actual), len(predicted & actual))


def false_positive_rate(predicted: set[str], innocent: set[str]) -> float:
    """Share of known-legitimate vouchers that were wrongly flagged.

    The decoy measurement. A signal can reach perfect recall by flagging
    everything, and this is the number that exposes it.
    """
    return len(predicted & innocent) / len(innocent) if innocent else 0.0


def precision_at_k(ranked: Sequence[str], actual: set[str], k: int) -> float:
    """Precision over the first ``k`` items of a ranked queue.

    A reviewer works down a list with a finite budget, so what matters is how
    much of the top of that list deserved the attention.
    """
    if k <= 0:
        return 0.0
    top = ranked[:k]
    return sum(item in actual for item in top) / len(top) if top else 0.0
