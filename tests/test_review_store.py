"""Tests for the review trail: decisions, the store, and the engagement identity.

The property that matters is that the trail only ever grows. A review record
that can be edited is not a review record, and an engagement quality reviewer
asking "why was this dismissed?" six months later needs the answer to still be
there — including if the reviewer changed their mind.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from caguard.benchmark.generator import GeneratorConfig, generate
from caguard.review.decisions import MIN_NOTE_WORDS, Decision, ReviewAction
from caguard.review.engagement import Engagement, ledger_hash, open_engagement
from caguard.review.finding import RiskBand
from caguard.review.store import ReviewStore


@pytest.fixture(scope="module")
def lines():
    return generate(GeneratorConfig(seed=101, n_vouchers=400)).lines


@pytest.fixture
def store(tmp_path: Path) -> ReviewStore:
    return ReviewStore(tmp_path / "review.db")


@pytest.fixture
def engagement(store: ReviewStore, lines) -> Engagement:
    return store.open_engagement(open_engagement(lines, source="seed101.parquet"))


def decision(engagement: Engagement, **overrides) -> Decision:
    base = {
        "engagement_id": engagement.id,
        "voucher_id": "V000001",
        "action": ReviewAction.ACCEPT,
        "reviewer": "abirami",
    }
    return Decision(**{**base, **overrides})


# --- decisions ---------------------------------------------------------------


def test_rejecting_requires_a_reason(engagement: Engagement) -> None:
    """Someone will ask why this was dismissed. The answer must not be lost."""
    with pytest.raises(ValueError, match="needs a reason"):
        decision(engagement, action=ReviewAction.REJECT, note="no")


def test_a_reason_must_be_more_than_a_word(engagement: Engagement) -> None:
    with pytest.raises(ValueError, match=f"{MIN_NOTE_WORDS} words"):
        decision(engagement, action=ReviewAction.REJECT, note="fine")


def test_accepting_needs_no_reason(engagement: Engagement) -> None:
    """Accepting says 'I looked'. It is rejection that needs defending."""
    assert decision(engagement, action=ReviewAction.ACCEPT).note is None


def test_an_adjustment_must_name_a_band(engagement: Engagement) -> None:
    with pytest.raises(ValueError, match="which band"):
        decision(engagement, action=ReviewAction.ADJUST)


def test_an_adjustment_records_the_band(engagement: Engagement) -> None:
    moved = decision(engagement, action=ReviewAction.ADJUST, adjusted_band=RiskBand.LOW)
    assert moved.adjusted_band is RiskBand.LOW
    assert "moved to low" in moved.summary()


@pytest.mark.parametrize(
    "action,closing",
    [
        (ReviewAction.ACCEPT, True),
        (ReviewAction.REJECT, True),
        (ReviewAction.INVESTIGATE, False),
        (ReviewAction.ADJUST, False),
    ],
)
def test_which_actions_settle_a_finding(action: ReviewAction, closing: bool) -> None:
    assert action.is_closing is closing


def test_decisions_are_immutable(engagement: Engagement) -> None:
    made = decision(engagement)
    with pytest.raises(ValueError):
        made.action = ReviewAction.REJECT  # pyright: ignore[reportAttributeAccessIssue]


# --- the store ---------------------------------------------------------------


def test_the_trail_only_ever_grows(store: ReviewStore, engagement: Engagement) -> None:
    """A reviewer changing their mind is itself a fact worth keeping."""
    store.record(decision(engagement, action=ReviewAction.ACCEPT))
    store.record(
        decision(
            engagement,
            action=ReviewAction.REJECT,
            note="Traced to the signed lease agreement",
        )
    )
    trail = store.trail(engagement.id, "V000001")
    assert [d.action for d in trail] == [ReviewAction.ACCEPT, ReviewAction.REJECT]
    assert [d.sequence for d in trail] == sorted(d.sequence or 0 for d in trail)


def test_current_state_is_the_latest_decision(store: ReviewStore, engagement: Engagement) -> None:
    store.record(decision(engagement, action=ReviewAction.INVESTIGATE))
    store.record(decision(engagement, action=ReviewAction.ACCEPT))
    assert store.current(engagement.id)["V000001"].action is ReviewAction.ACCEPT
    assert len(store.trail(engagement.id, "V000001")) == 2


def test_the_store_never_issues_an_update_or_delete() -> None:
    """Enforced by reading the source, because a future edit would be silent."""
    source = Path("src/caguard/review/store.py").read_text().upper()
    assert "UPDATE DECISIONS" not in source
    assert "DELETE FROM DECISIONS" not in source


def test_counts_drive_the_progress_display(store: ReviewStore, engagement: Engagement) -> None:
    store.record(decision(engagement, voucher_id="V000001", action=ReviewAction.ACCEPT))
    store.record(decision(engagement, voucher_id="V000002", action=ReviewAction.ACCEPT))
    store.record(
        decision(
            engagement,
            voucher_id="V000003",
            action=ReviewAction.REJECT,
            note="Checked against the purchase order",
        )
    )
    counts = store.counts(engagement.id)
    assert counts[ReviewAction.ACCEPT] == 2
    assert counts[ReviewAction.REJECT] == 1


def test_a_decision_needs_an_open_engagement(store: ReviewStore) -> None:
    with pytest.raises(KeyError, match="no engagement"):
        store.record(
            Decision(
                engagement_id="nope",
                voucher_id="V1",
                action=ReviewAction.ACCEPT,
                reviewer="x",
            )
        )


def test_reopening_the_same_ledger_reuses_the_engagement(store: ReviewStore, lines) -> None:
    first = store.open_engagement(open_engagement(lines))
    second = store.open_engagement(open_engagement(lines))
    assert first.id == second.id
    assert len(store.engagements()) == 1


def test_the_database_survives_being_reopened(tmp_path: Path, lines) -> None:
    path = tmp_path / "review.db"
    first = ReviewStore(path)
    engagement = first.open_engagement(open_engagement(lines))
    first.record(
        Decision(
            engagement_id=engagement.id,
            voucher_id="V000001",
            action=ReviewAction.ACCEPT,
            reviewer="abirami",
        )
    )
    reopened = ReviewStore(path)
    assert len(reopened.trail(engagement.id)) == 1
    assert reopened.engagement(engagement.id) is not None


def test_timestamps_survive_a_round_trip(store: ReviewStore, engagement: Engagement) -> None:
    when = datetime(2026, 3, 31, 9, 30, tzinfo=UTC)
    store.record(decision(engagement, decided_at=when))
    assert store.trail(engagement.id)[0].decided_at == when


# --- engagement identity -----------------------------------------------------


def test_engagement_records_the_ledger_fingerprint(engagement: Engagement, lines) -> None:
    """Findings are recomputed, so the hash is how drift becomes detectable."""
    assert len(engagement.content_sha256) == 64
    assert engagement.matches(lines)


def test_a_different_ledger_does_not_match(engagement: Engagement) -> None:
    other = generate(GeneratorConfig(seed=999, n_vouchers=400)).lines
    assert not engagement.matches(other)


def test_the_hash_is_over_content_not_file_format(lines) -> None:
    """The same book saved as CSV or parquet is the same book."""
    shuffled = lines.sample(frac=1.0, random_state=7)
    assert ledger_hash(lines) == ledger_hash(shuffled)


def test_engagement_derives_its_name_from_the_ledger(lines) -> None:
    built = open_engagement(lines)
    assert "ACME-IN" in built.name
    assert "FY2024-25" in built.name
    assert built.voucher_count > 0
