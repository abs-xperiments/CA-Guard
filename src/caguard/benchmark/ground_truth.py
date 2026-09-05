"""The ground-truth artefact — written by the generator, read by no detector.

Kept in a file physically separate from the ledger so that the separation in
ADR-0003 is visible on disk, not merely asserted in prose. The evaluation
harness in Phase 7 joins the two on ``voucher_id``; nothing else may.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from caguard.benchmark.anomalies import AnomalyKind, DecoyKind

GROUND_TRUTH_VERSION = 1


class VoucherTruth(BaseModel):
    """What was planted in one voucher, and why."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    voucher_id: str
    anomalies: list[AnomalyKind] = Field(default_factory=list)
    decoys: list[DecoyKind] = Field(default_factory=list)
    note: str | None = None

    @property
    def is_anomalous(self) -> bool:
        return bool(self.anomalies)


class GroundTruth(BaseModel):
    """Every planted fact about one generated ledger."""

    model_config = ConfigDict(extra="forbid")

    version: int = GROUND_TRUTH_VERSION
    seed: int
    entity_id: str
    fiscal_year: str
    total_vouchers: int
    vouchers: list[VoucherTruth]

    @property
    def anomalous_ids(self) -> set[str]:
        return {v.voucher_id for v in self.vouchers if v.is_anomalous}

    @property
    def decoy_ids(self) -> set[str]:
        return {v.voucher_id for v in self.vouchers if v.decoys}

    @property
    def anomaly_rate(self) -> float:
        return len(self.anomalous_ids) / self.total_vouchers if self.total_vouchers else 0.0

    def ids_with(self, kind: AnomalyKind | DecoyKind) -> set[str]:
        """Voucher ids carrying a given planted kind — for per-type recall."""
        if isinstance(kind, AnomalyKind):
            return {v.voucher_id for v in self.vouchers if kind in v.anomalies}
        return {v.voucher_id for v in self.vouchers if kind in v.decoys}

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.model_dump(mode="json"), indent=2, sort_keys=True))

    @classmethod
    def read(cls, path: Path) -> GroundTruth:
        return cls.model_validate_json(path.read_text())
