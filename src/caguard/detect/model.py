"""The ML layer: an Isolation Forest over the voucher feature matrix.

An Isolation Forest gives an outlier score and no reason. That is acceptable
here only because it sits beside rules that do give reasons, and because its own
hit carries the feature values that put the voucher at the top. It must never be
the sole basis for a finding — the LLM in Phase 5 explains structured findings,
and "the model said so" is not one.

Determinism is not a nicety. A reviewer reopening an engagement must see the
same queue, and an evaluation that cannot be re-run cannot be published. Hence a
fixed seed, a pinned feature order, sorted inputs and a recorded version.

Fitted on the ledger under review, unsupervised. There is no training set and no
labels — which is what makes it applicable to a client whose books nobody has
ever seen.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from caguard.detect.context import LedgerContext
from caguard.detect.features import FEATURE_NAMES, build_features
from caguard.detect.types import DetectorConfig, SignalHit, SignalKind

#: Bumped whenever the feature set or the fitting procedure changes, because a
#: score is only comparable to another score from the same version.
MODEL_VERSION = "isolation-forest-1.0.0"

RANDOM_STATE = 20250906
N_ESTIMATORS = 200

#: How many features to name when explaining why a voucher scored as it did.
TOP_FEATURES = 3


@dataclass(frozen=True)
class ModelResult:
    """Scores for one ledger, plus what the model was."""

    scores: pd.Series
    version: str
    contamination: float
    feature_names: tuple[str, ...]

    @property
    def threshold(self) -> float:
        """Score above which a voucher is treated as outlying."""
        return float(np.quantile(self.scores, 1 - self.contamination))


def score_ledger(ctx: LedgerContext, config: DetectorConfig | None = None) -> ModelResult:
    """Fit an Isolation Forest on this ledger and score every voucher.

    Higher is more unusual. scikit-learn's raw scores run the other way, so they
    are negated here to keep "bigger means worse" true across every signal.
    """
    cfg = config or DetectorConfig()
    features = build_features(ctx).sort_index()

    forest = IsolationForest(
        n_estimators=N_ESTIMATORS,
        # scikit-learn types this as str | float; a float is the documented way
        # to pin the outlier share and is what we need for a review budget.
        contamination=cfg.model_contamination,  # pyright: ignore[reportArgumentType]
        random_state=RANDOM_STATE,
        n_jobs=1,  # single-threaded: parallel fitting is not bit-reproducible
    )
    forest.fit(features.to_numpy())
    scores = pd.Series(
        -forest.score_samples(features.to_numpy()), index=features.index, name="score"
    )
    return ModelResult(
        scores=scores,
        version=MODEL_VERSION,
        contamination=cfg.model_contamination,
        feature_names=FEATURE_NAMES,
    )


def detect_ml_anomaly(ctx: LedgerContext, config: DetectorConfig | None = None) -> list[SignalHit]:
    """Flag the vouchers the model considers most unusual.

    The reason names the features that stand furthest from the ledger's own
    median, so a reviewer has something to check rather than a bare score. That
    is an honest description of what drove the ranking, not a causal claim.
    """
    cfg = config or DetectorConfig()
    result = score_ledger(ctx, cfg)
    features = build_features(ctx).sort_index()

    median = features.median()
    spread = features.std(ddof=0).replace(0.0, np.nan)
    standardised = ((features - median).abs() / spread).fillna(0.0)

    threshold = result.threshold
    hits: list[SignalHit] = []
    for voucher_id, score in result.scores.items():
        if score < threshold:
            continue
        row = standardised.loc[voucher_id]
        drivers = row.nlargest(TOP_FEATURES)
        named = ", ".join(str(name) for name in drivers.index)
        hits.append(
            SignalHit(
                voucher_id=str(voucher_id),
                kind=SignalKind.ML_ANOMALY,
                strength=float(min(1.0, max(0.0, (score - threshold) / max(threshold, 1e-9)))),
                reason=(
                    f"Statistically unusual against the rest of this ledger; "
                    f"the largest differences are in {named}."
                ),
                evidence={
                    "model_version": result.version,
                    "score": round(float(score), 4),
                    "threshold": round(threshold, 4),
                    "contamination": result.contamination,
                    "top_features": {
                        str(name): round(float(features.loc[voucher_id, name]), 3)
                        for name in drivers.index
                    },
                },
            )
        )
    return sorted(hits, key=lambda hit: hit.voucher_id)
