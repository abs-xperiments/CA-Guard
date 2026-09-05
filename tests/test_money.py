from __future__ import annotations

from decimal import Decimal

import pytest

from caguard.money import (
    MoneyError,
    float_rupees_to_paise,
    format_inr,
    paise_to_rupees,
    rupees_to_paise,
)


@pytest.mark.parametrize(
    "rupees,paise",
    [("0.01", 1), ("1", 100), ("1234.56", 123456), ("-5.25", -525)],
)
def test_round_trip_is_exact(rupees: str, paise: int) -> None:
    assert rupees_to_paise(Decimal(rupees)) == paise
    assert paise_to_rupees(paise) == Decimal(rupees).quantize(Decimal("0.01"))


def test_floats_are_refused_not_rounded() -> None:
    """A float rupee amount must be an explicit decision, never a silent rounding."""
    with pytest.raises(MoneyError, match="float rupees are not accepted"):
        rupees_to_paise(1.5)  # pyright: ignore[reportArgumentType]


def test_sub_paisa_precision_is_refused() -> None:
    with pytest.raises(MoneyError, match="finer than one paisa"):
        rupees_to_paise(Decimal("1.005"))


def test_explicit_float_conversion_rounds_half_up() -> None:
    assert float_rupees_to_paise(1.005) == 101
    assert float_rupees_to_paise(0.1) == 10


def test_absurd_amounts_are_rejected_as_likely_mapping_errors() -> None:
    with pytest.raises(MoneyError, match="sanity limit"):
        rupees_to_paise(Decimal("99999999999"))


@pytest.mark.parametrize(
    "paise,formatted",
    [
        (500, "₹5.00"),
        (123456, "₹1,234.56"),
        (12345678, "₹1,23,456.78"),
        (1234567890, "₹1,23,45,678.90"),
        (-10000000, "-₹1,00,000.00"),
    ],
)
def test_indian_digit_grouping(paise: int, formatted: str) -> None:
    """Indian grouping is 2-2-3 from the right; a CA reads 3-3-3 as a wrong number."""
    assert format_inr(paise) == formatted
