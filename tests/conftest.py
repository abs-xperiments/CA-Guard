from __future__ import annotations

from datetime import date, datetime

import pytest

from caguard.benchmark.generator import GeneratedLedger, GeneratorConfig, generate
from caguard.schema import AccountGroup, JournalLine, VoucherType


@pytest.fixture(scope="session")
def ledger() -> GeneratedLedger:
    """One generated ledger shared across tests; generation is deterministic."""
    return generate(GeneratorConfig(n_vouchers=2000))


@pytest.fixture
def line_kwargs() -> dict[str, object]:
    """Minimal valid JournalLine arguments, for tests that vary one field."""
    return {
        "line_id": "V1-01",
        "voucher_id": "V1",
        "line_number": 1,
        "entity_id": "ACME-IN",
        "fiscal_year": "FY2024-25",
        "period": 1,
        "voucher_date": date(2024, 4, 15),
        "posted_at": datetime(2024, 4, 15, 11, 30),  # noqa: DTZ001
        "voucher_type": VoucherType.JOURNAL,
        "account_code": "1000",
        "account_name": "Cash in Hand",
        "account_group": AccountGroup.ASSET,
        "created_by": "rmehta",
        "debit_paise": 100_00,
    }


@pytest.fixture
def make_line(line_kwargs: dict[str, object]):
    def _make(**overrides: object) -> JournalLine:
        return JournalLine(**{**line_kwargs, **overrides})  # pyright: ignore[reportArgumentType]

    return _make
