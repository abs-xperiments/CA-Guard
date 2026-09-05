"""Money handling.

Amounts are held as **integer paise**, never as floats.

A float rupee cannot represent 0.1 exactly, so a ledger of a few thousand lines
drifts by fractions of a paisa and voucher balance checks start needing a fudge
tolerance. In an accounting tool that tolerance is exactly where a real
imbalance would hide. Integers remove the problem instead of hiding it: a
voucher balances when its paise sum is 0, with no epsilon anywhere.

The Pydantic contract speaks ``Decimal`` rupees because that is what an
accountant reads; the DataFrame layer speaks ``int64`` paise because that is
what arithmetic should touch. This module is the only place the two meet.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

PAISE_PER_RUPEE = 100

# Guardrail against a mis-parsed column silently becoming a nine-figure amount.
# ~ ₹1,000 crore, comfortably above any line a mid-size Indian firm would post.
MAX_ABS_PAISE = 10_000_000_000_00


class MoneyError(ValueError):
    """Raised when a value cannot be represented exactly as paise."""


def rupees_to_paise(value: Decimal | int | str) -> int:
    """Convert rupees to integer paise, refusing anything finer than a paisa.

    Floats are deliberately not accepted: ``0.07`` is not 7 paise, and silently
    rounding it is how rounding bugs enter an accounting system. Callers holding
    a float must decide explicitly (see :func:`float_rupees_to_paise`).
    """
    if isinstance(value, float):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise MoneyError(
            "float rupees are not accepted; use Decimal/str, "
            "or float_rupees_to_paise() to round explicitly"
        )
    try:
        dec = Decimal(value)
    except (InvalidOperation, TypeError) as exc:
        raise MoneyError(f"not a valid rupee amount: {value!r}") from exc

    if not dec.is_finite():
        raise MoneyError(f"rupee amount must be finite: {value!r}")

    scaled = dec * PAISE_PER_RUPEE
    if scaled != scaled.to_integral_value():
        raise MoneyError(f"amount finer than one paisa: {value!r}")

    paise = int(scaled)
    _check_range(paise)
    return paise


def float_rupees_to_paise(value: float) -> int:
    """Round a float rupee amount to the nearest paisa.

    Only for data that arrives as float from an external source (parquet, CSV).
    Never for amounts CA-Guard computes itself.
    """
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise MoneyError(f"not a valid rupee amount: {value!r}") from exc
    if not dec.is_finite():
        raise MoneyError(f"rupee amount must be finite: {value!r}")
    paise = int((dec * PAISE_PER_RUPEE).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    _check_range(paise)
    return paise


def paise_to_rupees(paise: int) -> Decimal:
    """Convert integer paise back to a 2-decimal-place ``Decimal`` of rupees."""
    return (Decimal(paise) / PAISE_PER_RUPEE).quantize(Decimal("0.01"))


def format_inr(paise: int) -> str:
    """Format paise in the Indian grouping convention (lakh/crore).

    ``12345678`` → ``"₹1,23,456.78"``. Indian digit grouping is 2-2-3 from the
    right, not 3-3-3, and a CA reads the wrong grouping as a wrong number.
    """
    sign = "-" if paise < 0 else ""
    whole, frac = divmod(abs(paise), PAISE_PER_RUPEE)
    digits = str(whole)
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups: list[str] = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join([*groups, tail])
    return f"{sign}₹{digits}.{frac:02d}"


def _check_range(paise: int) -> None:
    if abs(paise) > MAX_ABS_PAISE:
        raise MoneyError(
            f"amount {paise} paise exceeds the sanity limit of {MAX_ABS_PAISE}; "
            "this usually means a column was mapped or parsed incorrectly"
        )
