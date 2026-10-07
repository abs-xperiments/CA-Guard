"""Browser tests against the real stack: the built workspace in front of the API.

Run with ``make e2e`` (or ``CAGUARD_E2E=1 uv run pytest tests/e2e``). They are
skipped otherwise, because they need ``web/`` built, ports 8000 and 3999 free,
and a headless Chromium (``uv run playwright install chromium``).
"""

from __future__ import annotations

import io
import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from stack import Stack, running_stack  # noqa: E402

from caguard.benchmark.generator import GeneratorConfig, generate  # noqa: E402

if os.environ.get("CAGUARD_E2E") != "1":
    pytest.skip("browser tests: set CAGUARD_E2E=1 (make e2e)", allow_module_level=True)

from playwright.sync_api import Browser, Page, sync_playwright  # noqa: E402

TEST_PASSPHRASE = "correct-horse-battery-9"


@pytest.fixture(scope="session")
def stack() -> Iterator[Stack]:
    with running_stack() as running:
        yield running


@pytest.fixture(scope="session")
def browser() -> Iterator[Browser]:
    with sync_playwright() as playwright:
        launched = playwright.chromium.launch()
        yield launched
        launched.close()


@pytest.fixture
def page(browser: Browser) -> Iterator[Page]:
    context = browser.new_context(accept_downloads=True)
    opened = context.new_page()
    yield opened
    context.close()


@pytest.fixture(scope="session")
def ledger_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A synthetic ledger, as a client would hand it over: a CSV file."""
    path = tmp_path_factory.mktemp("ledgers") / "Sharma Traders FY25.csv"
    buffer = io.StringIO()
    generate(GeneratorConfig(seed=20250906, n_vouchers=1200)).lines.to_csv(buffer, index=False)
    path.write_text(buffer.getvalue())
    return path
