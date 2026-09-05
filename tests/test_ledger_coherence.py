"""The internal CA review, turned into tests.

An audit of the first generated ledger (``docs/ca_validation/findings.md``)
found that it was a stream of vouchers rather than a set of books: each one
balanced, but together they left the bank overdrawn by ₹5.58 crore, fixed
assets in credit, and a full year of undischarged TDS. A reviewer would have
stopped at the second line of the trial balance.

None of that was visible to the Phase 1 tests, which checked vouchers one at a
time. These tests read the ledger the way a reviewer opens a client file —
balances first — so the same class of defect cannot return unnoticed.
"""

from __future__ import annotations

import pandas as pd
import pytest

from caguard.benchmark.generator import GeneratedLedger, GeneratorConfig, generate

CRORE = 1_00_00_000_00


@pytest.fixture(scope="module", params=(101, 102, 103), ids=lambda s: f"seed{s}")
def books(request: pytest.FixtureRequest) -> GeneratedLedger:
    return generate(GeneratorConfig(seed=request.param, n_vouchers=3000))


@pytest.fixture(scope="module")
def balances(books: GeneratedLedger) -> dict[str, int]:
    """Closing balance per account: positive is a debit balance."""
    frame = books.lines
    net = (
        frame.groupby("account_code").debit_paise.sum()
        - frame.groupby("account_code").credit_paise.sum()
    )
    return {str(code): int(value) for code, value in net.items()}


def test_trial_balance_nets_to_zero(balances: dict[str, int]) -> None:
    assert sum(balances.values()) == 0


def test_opening_balances_exist(books: GeneratedLedger) -> None:
    """F-2. A company does not appear on 1 April with nothing and trade ₹10 crore."""
    opening = books.lines[books.lines.voucher_type == "opening_balance"]
    assert not opening.empty
    assert opening.voucher_id.nunique() == 1
    assert int(opening.debit_paise.sum()) == int(opening.credit_paise.sum())
    assert "3000" in set(opening.account_code), "no share capital brought forward"


def test_bank_is_not_overdrawn(balances: dict[str, int]) -> None:
    """F-1. A credit balance on a current account with no facility is impossible."""
    assert balances["1010"] > 0, "bank account is overdrawn"


def test_cash_in_hand_is_plausible(balances: dict[str, int]) -> None:
    """F-13. A company does not sit on crores of physical cash."""
    assert 0 < balances["1000"] < 25_00_000_00


def test_fixed_assets_carry_a_debit_balance(balances: dict[str, int]) -> None:
    """F-3. Depreciation accumulates separately; the asset stays at cost.

    Schedule II expects gross block, depreciation and net block to be visible.
    Crediting the asset directly hides all three and eventually turns a fixed
    asset into a liability.
    """
    assert balances["1500"] > 0, "Plant & Machinery is in credit"
    assert balances["1590"] < 0, "Accumulated Depreciation is not a credit balance"
    assert abs(balances["1590"]) < balances["1500"], "asset is fully written down"


def test_term_loan_is_a_liability(balances: dict[str, int]) -> None:
    """F-5. Repaying a loan that was never drawn leaves it in debit."""
    assert balances["2500"] < 0


def test_receivables_and_payables_have_the_right_sign(balances: dict[str, int]) -> None:
    assert balances["1100"] > 0, "Sundry Debtors is in credit"
    assert balances["2000"] < 0, "Sundry Creditors is in debit"


@pytest.mark.parametrize(
    "code,label",
    [
        ("2202", "TDS on salary"),
        ("2200", "TDS 194C"),
        ("2201", "TDS 194J"),
        ("2100", "GST payable CGST"),
        ("2101", "GST payable SGST"),
        ("2310", "PF payable"),
        ("2300", "Salaries payable"),
    ],
)
def test_statutory_dues_are_discharged_during_the_year(
    books: GeneratedLedger, balances: dict[str, int], code: str, label: str
) -> None:
    """F-4 and F-7. Dues are remitted monthly; only the last month stays open.

    A year of unpaid TDS would be a reportable matter in a real engagement — and
    here it also meant an entire class of ordinary transactions was missing from
    the population the detectors learn "normal" from.
    """
    turnover = -balances.get("4000", 0)
    outstanding = abs(balances.get(code, 0))
    assert outstanding < turnover * 0.10, (
        f"{label} of {outstanding / 100:,.0f} rupees looks like a full year unpaid"
    )


def test_remittance_vouchers_actually_appear(books: GeneratedLedger) -> None:
    narrations = " ".join(books.lines.narration.dropna().astype(str))
    for expected in ("TDS remitted", "Provident fund contribution remitted", "GST discharged"):
        assert expected in narrations, f"no voucher says {expected!r}"


def test_working_capital_days_are_plausible(balances: dict[str, int]) -> None:
    """F-6. Collections and payments must track the invoices that created them."""
    turnover = -balances["4000"]
    purchases = balances["5000"]
    assert balances["1100"] / turnover * 365 < 150, "debtor days too high"
    assert abs(balances["2000"]) / purchases * 365 < 150, "creditor days too high"


def test_gross_margin_is_plausible(balances: dict[str, int]) -> None:
    """A trading company at an 8% gross margin is losing money, and the bank shows it."""
    turnover = -balances["4000"]
    margin = 1 - balances["5000"] / turnover
    assert 0.15 <= margin <= 0.60, f"gross margin of {margin:.0%} is not plausible"


def test_payroll_is_monthly_not_random(books: GeneratedLedger) -> None:
    """Salary is a monthly run.

    Drawing it at random produced roughly 280 payroll runs in one year and
    ₹39 crore of wages against ₹8 crore of sales.
    """
    payroll = books.lines[books.lines.narration.astype(str).str.startswith("Salary payable")]
    assert payroll.voucher_id.nunique() == 12


def test_provident_fund_respects_the_statutory_ceiling(balances: dict[str, int]) -> None:
    """F-8. PF is 12% of basic, capped at ₹15,000 basic — ₹1,800 per head per month."""
    wages = balances["5100"]
    assert abs(balances["2310"]) < wages * 0.12, "PF looks like 12% of gross"


def test_depreciation_is_charged_monthly(books: GeneratedLedger) -> None:
    """F-10. A company preparing periodic accounts depreciates monthly."""
    monthly = books.lines[
        books.lines.narration.astype(str).str.contains("Depreciation charged for the month")
    ]
    assert monthly.voucher_id.nunique() == 12


def test_cash_payments_stay_under_the_disallowance_threshold(books: GeneratedLedger) -> None:
    """F-13. Section 40A(3) disallows cash payments above ₹10,000."""
    lines = books.lines
    cash_credits = lines[(lines.account_code == "1000") & (lines.credit_paise > 0)]
    assert (cash_credits.credit_paise <= 10_000_00).all()


def test_every_voucher_still_balances(books: GeneratedLedger) -> None:
    """The Phase 1 guarantee survives the restructure."""
    sums = books.lines.groupby("voucher_id").apply(
        lambda g: int(g.debit_paise.sum() - g.credit_paise.sum()), include_groups=False
    )
    assert (sums == 0).all()


def test_ledger_still_reproduces_from_a_seed() -> None:
    a = generate(GeneratorConfig(seed=77, n_vouchers=400))
    b = generate(GeneratorConfig(seed=77, n_vouchers=400))
    assert a.manifest["content_sha256"] == b.manifest["content_sha256"]
    pd.testing.assert_frame_equal(a.lines, b.lines)
