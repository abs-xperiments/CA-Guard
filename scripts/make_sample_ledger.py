"""Write the sample ledger the workspace offers to first-time users and demo visitors.

    uv run python scripts/make_sample_ledger.py

The product never generates it at runtime: ADR-0003 forbids anything outside
the benchmark from importing the generator, or the detectors could in principle
see how the data was made and every published metric would become circular.
So it is generated here, once, and committed as a compressed file the API only
reads.

It is written the way Tally exports a day book — "Voucher No", "Ledger",
rupee amounts with Indian grouping, dates as DD-MM-YYYY — so that a visitor sees
CA-Guard read a familiar export rather than its own internal format. The seed
is neither a held-out nor a tuning seed of the benchmark.
"""

from __future__ import annotations

import gzip
import io
from pathlib import Path

import pandas as pd

from caguard.benchmark.generator import GeneratorConfig, generate
from caguard.money import format_inr

#: Not in HELD_OUT_SEEDS or TUNING_SEEDS (tests/test_sample_ledger.py checks).
SAMPLE_SEED = 20251001
VOUCHERS = 1500

OUT = Path(__file__).resolve().parent.parent / "src/caguard/api/assets/sample_ledger.csv.gz"


def tally_style(lines: pd.DataFrame) -> pd.DataFrame:
    """The canonical ledger, re-expressed as a Tally day-book export."""
    posted = pd.to_datetime(lines["posted_at"])
    return pd.DataFrame(
        {
            "Voucher No": lines["voucher_id"],
            "Date": pd.to_datetime(lines["voucher_date"]).dt.strftime("%d-%m-%Y"),
            "Posted": posted.dt.strftime("%d-%m-%Y %H:%M").fillna(""),
            "Vch Type": lines["voucher_type"].astype(str).str.replace("_", " ").str.title(),
            "Ledger": lines["account_name"],
            "Debit": [format_inr(int(v)) if v else "" for v in lines["debit_paise"]],
            "Credit": [format_inr(int(v)) if v else "" for v in lines["credit_paise"]],
            "Narration": lines["narration"].fillna(""),
            "Doc Ref": lines["document_ref"].fillna(""),
            "Entered By": lines["created_by"],
            "Approved By": lines["approved_by"].fillna(""),
        }
    )


def main() -> None:
    lines = generate(GeneratorConfig(seed=SAMPLE_SEED, n_vouchers=VOUCHERS)).lines
    buffer = io.StringIO()
    tally_style(lines).to_csv(buffer, index=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # mtime=0 so regenerating the same ledger gives the same bytes.
    with OUT.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as packed:
        packed.write(buffer.getvalue().encode())
    print(f"wrote {OUT} ({OUT.stat().st_size:,} bytes, {len(lines):,} lines)")


if __name__ == "__main__":
    main()
