"""The whole review, as a reviewer does it, in a real browser.

Upload → findings → open one → its working, transaction and source rows →
explanation → decisions by keyboard and by button → the original file, byte
for byte → the report → a deep link → search → sign out.

API tests cannot see what these can: a proxy cutting uploads short, a
security policy blocking the page's own scripts, a shortcut firing behind a
dialog. Each of those happened during development.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from playwright.sync_api import Page, expect
from stack import Stack

from .conftest import TEST_PASSPHRASE

TIMEOUT = 60_000


def _sign_up(page: Page, stack: Stack, email: str, name: str) -> None:
    page.goto(f"{stack.web}/signup")
    page.get_by_label("Your name").fill(name)
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password").fill(TEST_PASSPHRASE)
    invite = page.get_by_label("Invite code")
    if invite.count():
        # After the first account, a colleague needs the firm's code — read the
        # way an administrator would, from the data directory.
        invite.fill((stack.data_dir / "invite.code").read_text().strip())
    page.get_by_role("button", name="Create account").click()
    expect(page.get_by_role("heading", name="Open a ledger for review")).to_be_visible()


def _upload(page: Page, ledger: Path) -> None:
    page.locator("input[type=file]").set_input_files(str(ledger))
    page.wait_for_url(re.compile(r"/review/[0-9a-f]{16}"), timeout=TIMEOUT)
    expect(page.locator("tbody tr").first).to_be_visible(timeout=TIMEOUT)


def test_the_whole_review_journey(page: Page, stack: Stack, ledger_file: Path) -> None:
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

    _sign_up(page, stack, "partner@firm.in", "R. Iyer")
    _upload(page, ledger_file)

    # Open the top finding: the explanation card, not just a list of codes.
    page.locator("tbody tr").first.click()
    drawer = page.get_by_role("complementary")
    expect(drawer.get_by_text(re.compile(r"^Prioritised for review"))).to_be_visible()
    expect(drawer.get_by_text("does not, by itself, establish")).to_be_visible()
    expect(
        drawer.get_by_role("heading", name=re.compile("Why this was flagged", re.I))
    ).to_be_visible()
    expect(drawer.get_by_text(re.compile(r"\d+ of \d+ expected items present"))).to_be_visible()
    expect(
        drawer.get_by_role("heading", name=re.compile("Suggested review steps", re.I))
    ).to_be_visible()

    # The transaction, and where it sits in the client's file.
    expect(drawer.get_by_text(re.compile(r"Sharma Traders FY25\.csv"))).to_be_visible()
    drawer.get_by_role("button", name="View in file").click()
    dialog = page.get_by_role("dialog")
    expect(dialog.get_by_text("Showing the rows behind this finding")).to_be_visible()
    expect(dialog.locator("tr.bg-accent-soft").first).to_be_visible()

    # A decision key pressed while the file is open must do nothing.
    voucher = drawer.locator("span.font-mono").first.inner_text()
    page.keyboard.press("e")
    page.keyboard.press("Escape")
    expect(dialog).to_be_hidden()
    expect(
        page.get_by_text(re.compile(rf"Recorded as an exception to follow up {voucher}"))
    ).to_have_count(0)

    # The explanation in a paragraph — with no model installed, CA-Guard's own.
    drawer.get_by_role("button", name="Explain this finding").click()
    expect(drawer.get_by_text("Written by CA-Guard")).to_be_visible(timeout=TIMEOUT)

    # Decide by keyboard: the toast says what happened and offers undo.
    page.keyboard.press("e")
    expect(page.get_by_text(f"Recorded as an exception to follow up {voucher}")).to_be_visible()
    expect(page.get_by_role("button", name="Undo")).to_be_visible()

    # The drawer holds the decided finding for a beat (the button shows a tick),
    # then moves on — wait for that, as a person reading it would.
    expect(drawer.locator("span.font-mono").first).not_to_have_text(voucher, timeout=TIMEOUT)
    second = drawer.locator("span.font-mono").first.inner_text()

    # Clearing needs a reason.
    note = page.get_by_placeholder(re.compile("Required when clearing"))
    clear = page.get_by_role("button", name=re.compile("Cleared — not a concern"))
    expect(clear).to_be_disabled()
    note.fill("Invoice seen and agreed to the ledger amount")
    expect(clear).to_be_enabled()
    clear.click()
    expect(page.get_by_text(re.compile(r"^Recorded as cleared"))).to_be_visible()

    # The original file, exactly as uploaded.
    page.get_by_role("button", name="Source").click()
    with page.expect_download() as download:
        page.get_by_role("dialog").get_by_role("link", name="Download original").click()
    saved = Path(download.value.path())
    assert (
        hashlib.sha256(saved.read_bytes()).digest()
        == hashlib.sha256(ledger_file.read_bytes()).digest()
    ), "the downloaded original must be byte-identical to the upload"
    page.keyboard.press("Escape")

    # The report, separating what CA-Guard saw from what the reviewer decided.
    with page.context.expect_page() as report_tab:
        page.get_by_role("link", name="Report").first.click()
    report = report_tab.value
    expect(report.get_by_text("What the reviewer decided")).to_be_visible()
    exception_row = report.get_by_role("row").filter(has_text=voucher)
    expect(exception_row).to_contain_text("Exception — follow up")
    expect(report.get_by_role("row").filter(has_text=second)).to_contain_text(
        "Cleared — not a concern"
    )
    expect(report.get_by_text("Invoice seen and agreed to the ledger amount")).to_be_visible()
    report.close()

    # A deep link opens the finding after a reload.
    page.goto(f"{page.url.split('?')[0]}?finding={voucher}")
    expect(page.get_by_role("complementary").locator("span.font-mono").first).to_have_text(voucher)

    # Search narrows the queue; a nonsense search says so plainly.
    page.keyboard.press("Escape")
    page.get_by_role("button", name="All").last.click()  # status: every finding
    page.get_by_label("Search findings").fill(voucher)
    expect(page.locator("tbody tr")).to_have_count(1)
    page.get_by_label("Search findings").fill("zzzz-nothing-matches")
    expect(page.get_by_text("No findings match")).to_be_visible()

    assert not errors, f"console errors: {errors}"


def test_a_file_ca_guard_cannot_read_is_explained(page: Page, stack: Stack, tmp_path: Path) -> None:
    _sign_up(page, stack, "article@firm.in", "Article Clerk")
    broken = tmp_path / "Trial balance.csv"
    broken.write_bytes(b"\x00\x01\x02 this is not a ledger")

    page.locator("input[type=file]").set_input_files(str(broken))

    alert = page.get_by_role("alert").filter(has_text="was not opened")
    expect(alert).to_be_visible(timeout=TIMEOUT)
    expect(alert).to_contain_text("Trial balance.csv")
    expect(alert).to_contain_text("Nothing was saved")
    expect(page.get_by_role("button", name="Try the same file again")).to_be_visible()


def test_signing_out_ends_the_session(page: Page, stack: Stack) -> None:
    _sign_up(page, stack, "manager@firm.in", "Audit Manager")
    page.get_by_role("button", name="Sign out").click()
    page.wait_for_url(re.compile(r"/login"), timeout=TIMEOUT)

    page.goto(stack.web)
    page.wait_for_url(re.compile(r"/login"), timeout=TIMEOUT)
    assert page.request.get(f"{stack.web}/api/engagements").status == 401
