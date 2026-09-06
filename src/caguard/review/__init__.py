"""Turning signals into a prioritised review queue a professional can work through.

Everything here is downstream of detection. The signals decide *what* is worth
noticing; this package decides *what to look at first*, and — more importantly —
records the arithmetic so a reviewer who disagrees can see the working.
"""

from caguard.review.evidence import EvidenceScore, score_evidence
from caguard.review.finding import Finding, RiskBand
from caguard.review.fusion import SIGNAL_WEIGHTS, build_findings, fuse

__all__ = [
    "SIGNAL_WEIGHTS",
    "EvidenceScore",
    "Finding",
    "RiskBand",
    "build_findings",
    "fuse",
    "score_evidence",
]
