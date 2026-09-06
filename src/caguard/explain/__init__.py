"""Explaining a finding that has already been computed.

The single rule this package exists to enforce:

    The model **renders** a Finding. It does not produce one, does not rank one,
    and may never reach an audit conclusion of its own.

Detection, scoring and ranking are all finished before a token is generated. If
no model is installed, or it errors, or its output fails the guard, the review
queue is unchanged and a written explanation still appears. That is not a
degraded mode — it is the normal mode with prose attached.
"""

from caguard.explain.deterministic import explain_deterministically
from caguard.explain.guard import GuardResult, check_grounding
from caguard.explain.provider import (
    ExplanationProvider,
    NullProvider,
    ProviderError,
    StubProvider,
)
from caguard.explain.service import Explanation, ExplanationService, Source

__all__ = [
    "Explanation",
    "ExplanationProvider",
    "ExplanationService",
    "GuardResult",
    "NullProvider",
    "ProviderError",
    "Source",
    "StubProvider",
    "check_grounding",
    "explain_deterministically",
]
