"""Deterministic generator for a synthetic Indian general ledger.

Produces a year of book-keeping for a mid-size Indian private limited company,
with a small number of planted irregularities and a larger number of legitimate
look-alikes. Given the same seed it produces the same ledger, byte for byte in
content-hash terms, so an evaluation can be re-run and checked by someone else.

The design answers the Phase 0 finding directly. The VynFi corpus labelled rows
"DuplicatePayment" without making them duplicates, which makes its labels
useless for measuring anything. Here every planted anomaly is *actually present
in the observable fields*, and ``tests/test_generator.py`` re-runs the same lift
test that exposed VynFi against this generator's own output. If a label ever
stops being grounded, CI fails.

Nothing in this module may be imported by a detector (ADR-0003 rule 1).
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from random import Random

import pandas as pd

from caguard.benchmark import coa
from caguard.benchmark.anomalies import AnomalyKind, DecoyKind
from caguard.benchmark.ground_truth import GroundTruth, VoucherTruth
from caguard.schema import (
    TimeFidelity,
    VoucherType,
    fiscal_period_of,
    fiscal_year_of,
)

GENERATOR_VERSION = "2.0.0"

MONTHS_IN_YEAR = 12

#: One leg of a voucher: account code, debit paise, credit paise.
Leg = tuple[str, int, int]


@dataclass(frozen=True)
class GeneratorConfig:
    """Knobs for one generated ledger.

    ``anomaly_rate`` defaults to 2%, inside the 1–3% band ADR-0003 rule 3
    requires. A convenient 20% would make every metric look better and mean
    nothing, because a real ledger does not contain 20% irregularities.

    ``n_vouchers`` is a target for the business population, not an exact count.
    An invoice and its settlement are one event and two vouchers, and the
    statutory remittances that follow depend on what the year actually accrued,
    so the ledger lands a little above the figure asked for.
    """

    seed: int = 20250906
    entity_id: str = "ACME-IN"
    fy_start_year: int = 2024
    n_vouchers: int = 4000
    anomaly_rate: float = 0.02
    decoy_rate: float = 0.05

    def __post_init__(self) -> None:
        if not 0.01 <= self.anomaly_rate <= 0.03:
            raise ValueError(
                f"anomaly_rate {self.anomaly_rate} is outside the 1–3% band required by "
                "ADR-0003 rule 3; a higher rate flatters every metric and models no real ledger"
            )
        if self.n_vouchers < 200:
            raise ValueError("n_vouchers must be >= 200 for every planted kind to appear")

    @property
    def fiscal_year(self) -> str:
        return f"FY{self.fy_start_year}-{(self.fy_start_year + 1) % 100:02d}"

    @property
    def fy_start(self) -> date:
        return date(self.fy_start_year, 4, 1)

    @property
    def fy_end(self) -> date:
        return date(self.fy_start_year + 1, 3, 31)


@dataclass
class GeneratedLedger:
    """A generated ledger plus the truth about it, kept as separate objects."""

    lines: pd.DataFrame
    truth: GroundTruth
    manifest: dict[str, object] = field(default_factory=dict)


# Columns in canonical order. Fixed so the content hash is stable across runs.
COLUMNS: tuple[str, ...] = (
    "line_id",
    "voucher_id",
    "line_number",
    "entity_id",
    "fiscal_year",
    "period",
    "voucher_date",
    "posted_at",
    "time_fidelity",
    "voucher_type",
    "account_code",
    "account_name",
    "account_group",
    "debit_paise",
    "credit_paise",
    "currency",
    "created_by",
    "approved_by",
    "document_ref",
    "narration",
    "cost_centre",
    "is_manual",
    "is_post_close",
)


class _Builder:
    """Accumulates vouchers. One instance per generation run, seeded once."""

    def __init__(self, config: GeneratorConfig) -> None:
        self.cfg = config
        # Seeded once per run: reproducibility, not cryptography.
        self.rng = Random(config.seed)
        self.rows: list[dict[str, object]] = []
        self.truth: list[VoucherTruth] = []
        self._seq = 0
        self._occurrences: dict[str, int] = {}
        #: Running petty-cash balance. Cash cannot go negative, so withdrawals
        #: and cash payments have to be driven by what is actually in the tin
        #: rather than by a weighting that only balances on average.
        self.cash_paise = 0

    def occurrence(self, kind: str) -> int:
        """How many times this pattern has been emitted so far, 0-based.

        Lets a monthly pattern land in a different month each time instead of
        clustering: a ledger with four rent payments on 1 April is one a CA
        would reject on sight.
        """
        seen = self._occurrences.get(kind, 0)
        self._occurrences[kind] = seen + 1
        return seen

    # --- primitives ----------------------------------------------------------

    def next_voucher_id(self, prefix: str = "V") -> str:
        self._seq += 1
        return f"{prefix}{self._seq:06d}"

    def working_day(self, *, allow_saturday: bool = True) -> date:
        """A random day in the fiscal year, Monday–Saturday.

        Saturday is a working day in most Indian firms — which is exactly why
        Sunday, not "the weekend", is the anomalous case.
        """
        span = (self.cfg.fy_end - self.cfg.fy_start).days
        while True:
            day = self.cfg.fy_start + timedelta(days=self.rng.randint(0, span))
            weekday = day.weekday()
            if weekday == 6 or (weekday == 5 and not allow_saturday):
                continue
            return day

    def business_time(
        self, day: date, *, lag_days: int | None = None, allow_sunday: bool = False
    ) -> datetime:
        """A plausible posting timestamp: same day or a day or two later, in office hours.

        The lag never lands on a Sunday unless asked. Without that, an ordinary
        Saturday voucher posted "one day later" becomes a Sunday entry, and the
        weekend signal fills up with vouchers nobody actually touched.
        """
        if lag_days is None:
            lag_days = self.rng.choices([0, 1, 2, 3], weights=[60, 25, 10, 5])[0]
        posted_day = day + timedelta(days=lag_days)
        while posted_day.weekday() == 6 and not allow_sunday:
            posted_day += timedelta(days=1)
        lo, hi = coa.BUSINESS_HOURS
        return datetime(  # noqa: DTZ001 — books are kept in local time; no tz in the source data
            posted_day.year,
            posted_day.month,
            posted_day.day,
            self.rng.randint(lo, hi - 1),
            self.rng.randrange(0, 60),
            self.rng.randrange(0, 60),
        )

    def amount_paise(self, mu: float = 11.3, sigma: float = 0.85) -> int:
        """A plausible, deliberately non-round transaction value.

        Real invoices carry odd paise. Making ordinary amounts non-round is what
        gives the round-number signal something to find.
        """
        rupees = self.rng.lognormvariate(mu, sigma)
        paise = int(rupees * 100)
        if paise % 100 == 0:  # nudge off an accidental round figure
            paise += self.rng.randint(1, 99)
        return max(paise, 10_00)

    def doc_ref(self, kind: str) -> str:
        start = self.cfg.fy_start_year % 100
        return f"{kind}/{start}-{start + 1:02d}/{self.rng.randint(1, 9999):04d}"

    def preparer_for(self, codes: Sequence[str]) -> str:
        """A preparer whose normal scope covers these accounts, else anyone."""
        candidates = [
            person
            for person, scope in coa.PREPARER_SCOPE.items()
            if any(code in scope for code in codes)
        ]
        return self.rng.choice(candidates or list(coa.PREPARERS))

    def outsider_for(self, codes: Sequence[str]) -> str:
        """A preparer whose scope covers none of these accounts — the unusual case."""
        outsiders = [
            person
            for person, scope in coa.PREPARER_SCOPE.items()
            if not any(code in scope for code in codes)
        ]
        return self.rng.choice(outsiders)

    # --- voucher assembly ----------------------------------------------------

    def add(
        self,
        *,
        voucher_type: VoucherType,
        voucher_date: date,
        posted_at: datetime,
        legs: Sequence[Leg],
        narration: str,
        created_by: str | None = None,
        approved_by: str | None = None,
        document_ref: str | None = None,
        is_manual: bool = False,
        is_post_close: bool = False,
        voucher_id: str | None = None,
        anomalies: Sequence[AnomalyKind] = (),
        decoys: Sequence[DecoyKind] = (),
        note: str | None = None,
    ) -> str:
        """Append one voucher and record its truth. Refuses to emit an unbalanced voucher."""
        imbalance = sum(d - c for _, d, c in legs)
        if imbalance != 0:
            raise AssertionError(
                f"generator produced an unbalanced voucher ({imbalance} paise): {legs}"
            )

        vid = voucher_id or self.next_voucher_id()
        codes = [code for code, _, _ in legs]
        preparer = created_by or self.preparer_for(codes)

        for n, (code, debit, credit) in enumerate(legs, start=1):
            acct = coa.account(code)
            self.rows.append(
                {
                    "line_id": f"{vid}-{n:02d}",
                    "voucher_id": vid,
                    "line_number": n,
                    "entity_id": self.cfg.entity_id,
                    "fiscal_year": fiscal_year_of(voucher_date),
                    "period": fiscal_period_of(voucher_date),
                    "voucher_date": voucher_date,
                    "posted_at": posted_at,
                    "time_fidelity": TimeFidelity.DATE_AND_TIME.value,
                    "voucher_type": voucher_type.value,
                    "account_code": acct.code,
                    "account_name": acct.name,
                    "account_group": acct.group.value,
                    "debit_paise": debit,
                    "credit_paise": credit,
                    "currency": "INR",
                    "created_by": preparer,
                    "approved_by": approved_by,
                    "document_ref": document_ref,
                    "narration": narration,
                    "cost_centre": None,
                    "is_manual": is_manual,
                    "is_post_close": is_post_close,
                }
            )

        if anomalies or decoys:
            self.truth.append(
                VoucherTruth(
                    voucher_id=vid,
                    anomalies=list(anomalies),
                    decoys=list(decoys),
                    note=note,
                )
            )
        return vid

    # --- tax-aware leg builders (integer arithmetic keeps vouchers exact) -----

    def sales_legs(self, taxable: int) -> list[Leg]:
        cgst = taxable * (coa.GST_RATE_PCT // 2) // 100
        sgst = cgst
        return [
            ("1100", taxable + cgst + sgst, 0),
            ("4000", 0, taxable),
            ("2100", 0, cgst),
            ("2101", 0, sgst),
        ]

    def purchase_legs(self, taxable: int) -> list[Leg]:
        cgst = taxable * (coa.GST_RATE_PCT // 2) // 100
        sgst = cgst
        return [
            ("5000", taxable, 0),
            ("1300", cgst, 0),
            ("1301", sgst, 0),
            ("2000", 0, taxable + cgst + sgst),
        ]

    def expense_legs(self, code: str, gross: int, tds_pct: int, tds_account: str) -> list[Leg]:
        tds = gross * tds_pct // 100
        return [(code, gross, 0), (tds_account, 0, tds), ("1010", 0, gross - tds)]

    def salary_legs(self, gross: int) -> list[Leg]:
        """Payroll: gross wages, less TDS under section 192 and provident fund.

        PF is applied per employee against the ₹15,000 basic ceiling, not to the
        aggregate. Twelve percent of a whole payroll figure overstates the
        liability by a wide margin once salaries rise above that ceiling.
        """
        tds = gross * coa.TDS_192_PCT // 100
        basic_each = int(gross * coa.BASIC_SHARE_OF_GROSS) // coa.EMPLOYEE_COUNT
        pf = coa.EMPLOYEE_COUNT * (min(basic_each, coa.PF_CEILING_BASIC_PAISE) * coa.PF_PCT // 100)
        return [
            ("5100", gross, 0),
            ("2202", 0, tds),
            ("2310", 0, pf),
            ("2300", 0, gross - tds - pf),
        ]


# --- orchestration -----------------------------------------------------------


def _content_hash(frame: pd.DataFrame) -> str:
    """A stable hash of the ledger's *content*.

    Deliberately not a hash of the parquet file. Parquet embeds writer metadata,
    so file bytes can change when pyarrow is upgraded even though not one value
    moved. Hashing a canonical CSV rendering means "reproducible" keeps meaning
    the same thing across library versions.
    """
    canonical = frame.sort_values(["voucher_id", "line_number"])[list(COLUMNS)]
    return hashlib.sha256(canonical.to_csv(index=False).encode()).hexdigest()


def _reassign_ids(rows: list[dict[str, object]], truth: list[VoucherTruth]) -> list[VoucherTruth]:
    """Renumber vouchers in date order and rewrite the truth to match.

    Without this the generator leaks its own labels: anomalies are emitted
    before the ordinary background, so ``V000001`` would almost always be
    anomalous and a detector could 'learn' the voucher number. Sorting by date
    and renumbering destroys that channel.
    """
    order: dict[str, tuple[object, object, str]] = {}
    for row in rows:
        vid = str(row["voucher_id"])
        key = (row["voucher_date"], row["posted_at"], vid)
        if vid not in order or key < order[vid]:
            order[vid] = key

    remap = {
        old: f"V{n:06d}" for n, old in enumerate(sorted(order, key=lambda v: order[v]), start=1)
    }
    seen: dict[str, int] = {}
    for row in rows:
        new_vid = remap[str(row["voucher_id"])]
        seen[new_vid] = seen.get(new_vid, 0) + 1
        row["voucher_id"] = new_vid
        row["line_number"] = seen[new_vid]
        row["line_id"] = f"{new_vid}-{seen[new_vid]:02d}"

    return [t.model_copy(update={"voucher_id": remap[t.voucher_id]}) for t in truth]


#: A monthly charge can only occur twelve times in a fiscal year. Emitting more
#: would produce four rent payments on 1 April, which no CA would believe.
MONTHLY_DECOY_CAP: dict[DecoyKind, int] = {
    DecoyKind.LEGIT_ROUND_RENT: 12,
    DecoyKind.LEGIT_RECURRING_EMI: 12,
}


def _decoy_schedule(total: int) -> list[DecoyKind]:
    """Choose which decoys to emit, respecting the once-a-month ceiling."""
    counts = dict.fromkeys(DecoyKind, 0)
    order = list(DecoyKind)
    for i in range(total):
        for offset in range(len(order)):
            kind = order[(i + offset) % len(order)]
            if counts[kind] < MONTHLY_DECOY_CAP.get(kind, total):
                counts[kind] += 1
                break
    return [kind for kind in order for _ in range(counts[kind])]


def generate(config: GeneratorConfig | None = None) -> GeneratedLedger:
    """Generate one reproducible Indian ledger with planted truth.

    The same seed always yields the same content hash. Anomalies and decoys are
    distributed round-robin so that every kind appears in every run, which is
    what makes per-type recall reportable (ADR-0003 rule 5).
    """
    # Imported here, not at module scope: these modules all need _Builder from
    # this one, so a top-level import would be circular.
    from caguard.benchmark.cycles import (
        emit_depreciation,
        emit_opening_balances,
        emit_opening_settlements,
        emit_payroll,
        emit_statutory_settlements,
    )
    from caguard.benchmark.decoys import emit_decoy
    from caguard.benchmark.patterns import emit_anomaly, emit_normal

    cfg = config or GeneratorConfig()
    b = _Builder(cfg)

    target_anomalous = max(len(AnomalyKind), round(cfg.n_vouchers * cfg.anomaly_rate))
    target_decoys = max(len(DecoyKind), round(cfg.n_vouchers * cfg.decoy_rate))

    # The year opens from a position, not from nothing.
    emitted = emit_opening_balances(b)
    emitted += emit_opening_settlements(b)
    # Payroll and depreciation happen once a month, like the calendar says.
    for month in range(MONTHS_IN_YEAR):
        emitted += emit_depreciation(b, month)
        emitted += emit_payroll(b, month)
        emitted += emit_payroll(b, month, directors=True)

    for i in range(target_anomalous):
        emitted += emit_anomaly(b, list(AnomalyKind)[i % len(AnomalyKind)])
    for kind in _decoy_schedule(target_decoys):
        emitted += emit_decoy(b, kind)
    while emitted < cfg.n_vouchers:
        emitted += emit_normal(b)

    # Last, because it reads what everything else accrued: the month's TDS, PF
    # and net GST are discharged in the following month rather than invented.
    emitted += emit_statutory_settlements(b)

    truth_records = _reassign_ids(b.rows, b.truth)
    frame = pd.DataFrame(b.rows, columns=list(COLUMNS)).sort_values(
        ["voucher_id", "line_number"], ignore_index=True
    )
    frame["voucher_date"] = pd.to_datetime(frame["voucher_date"])
    frame["posted_at"] = pd.to_datetime(frame["posted_at"])

    truth = GroundTruth(
        seed=cfg.seed,
        entity_id=cfg.entity_id,
        fiscal_year=cfg.fiscal_year,
        total_vouchers=emitted,
        vouchers=sorted(truth_records, key=lambda t: t.voucher_id),
    )
    manifest: dict[str, object] = {
        "generator_version": GENERATOR_VERSION,
        "seed": cfg.seed,
        "entity_id": cfg.entity_id,
        "fiscal_year": cfg.fiscal_year,
        "vouchers": emitted,
        "lines": len(frame),
        "anomalous_vouchers": len(truth.anomalous_ids),
        "decoy_vouchers": len(truth.decoy_ids),
        "anomaly_rate": round(truth.anomaly_rate, 4),
        "content_sha256": _content_hash(frame),
    }
    return GeneratedLedger(lines=frame, truth=truth, manifest=manifest)


def iter_vouchers(frame: pd.DataFrame) -> Iterator[tuple[str, pd.DataFrame]]:
    """Group a ledger frame by voucher — the unit of review."""
    for vid, group in frame.groupby("voucher_id", sort=True):
        yield str(vid), group
