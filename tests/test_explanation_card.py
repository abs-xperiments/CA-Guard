"""The Explain Finding card: complete, deterministic, and held to the guard's own rules.

Phase 3 of the completion plan. The card is what a reviewer reads first, with
or without a model, so it is tested the way the model's prose is: nothing on it
may be invented, nothing may be left out, and nothing may conclude.
"""

from __future__ import annotations

import io
import math
import re
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from caguard.api.app import create_app
from caguard.benchmark.generator import GeneratorConfig, generate
from caguard.detect.context import build_context
from caguard.detect.types import SignalKind
from caguard.explain.card import LIMITATION, build_card
from caguard.explain.guard import FORBIDDEN_PHRASES
from caguard.explain.vocabulary import VOCABULARY, is_minor, mentions
from caguard.review.comparables import account_profile, primary_accounts, similar_entries
from caguard.review.fusion import build_findings


@pytest.fixture(scope="module")
def lines() -> pd.DataFrame:
    return generate(GeneratorConfig(seed=20250906, n_vouchers=1500)).lines


@pytest.fixture(scope="module")
def ctx(lines: pd.DataFrame):
    return build_context(lines)


@pytest.fixture(scope="module")
def findings(lines: pd.DataFrame, ctx):
    return build_findings(lines, context=ctx)


@pytest.fixture(scope="module")
def names(lines: pd.DataFrame) -> dict[str, str]:
    return dict(zip(lines.account_code.astype(str), lines.account_name.astype(str), strict=True))


@pytest.fixture(scope="module")
def cards(findings, ctx, names):
    flagged = {f.voucher_id for f in findings}
    return [(f, build_card(f, ctx, account_names=names, flagged=flagged)) for f in findings]


# --- one vocabulary, matching the detectors ----------------------------------------


def test_every_signal_kind_has_wording() -> None:
    assert set(VOCABULARY) == set(SignalKind)


def test_every_detector_reason_satisfies_its_own_cues(findings) -> None:
    """Otherwise the guard would reject CA-Guard's own deterministic text."""
    seen: set[SignalKind] = set()
    for finding in findings:
        for hit in finding.signals:
            assert mentions(hit.reason, hit.kind), (hit.kind, hit.reason)
            seen.add(hit.kind)
    assert len(seen) >= 8, f"the fixture should exercise most signals, saw {sorted(seen)}"


# --- the card is complete --------------------------------------------------------------


def test_every_finding_gets_a_complete_card(cards) -> None:
    for finding, card in cards:
        assert card.summary.startswith("Prioritised for review")
        assert card.limitation == LIMITATION
        assert [s.kind for s in card.signals] == [
            h.kind.value
            for h in sorted(finding.signals, key=lambda h: -finding.contributions.get(h.kind, 0))
        ]
        for signal in card.signals:
            assert signal.working, f"{signal.kind} has no working"
            for row in signal.working:
                assert row.value and row.value not in {"None", "nan", "?"}, (signal.kind, row)
        assert card.next_steps
        assert len(card.evidence) == 3


def test_contribution_levels_and_minor_flags_follow_the_numbers(cards) -> None:
    for _, card in cards:
        for signal in card.signals:
            assert signal.minor == is_minor(signal.contribution)
            expected = (
                "High"
                if signal.contribution >= 0.6
                else "Medium"
                if signal.contribution >= 0.3
                else "Low"
            )
            assert signal.level == expected


def test_minor_signals_never_headline_the_summary(cards) -> None:
    ml_phrase = VOCABULARY[SignalKind.ML_ANOMALY].phrase
    for _, card in cards:
        majors = [s for s in card.signals if not s.minor]
        if majors and all(s.kind != "ml_anomaly" for s in majors):
            assert ml_phrase not in card.summary


def test_nothing_on_the_card_concludes(cards) -> None:
    """CA-Guard's own words are held to the rule the model is held to."""
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(p) for p in FORBIDDEN_PHRASES) + r")\b", re.IGNORECASE
    )
    for _, card in cards:
        own_words = [
            card.summary,
            card.limitation,
            *card.next_steps,
            *[s.title for s in card.signals],
            *[s.standard or "" for s in card.signals],
            *[row.label for s in card.signals for row in s.working],
            *[item.detail for item in card.evidence],
        ]
        for text in own_words:
            assert not pattern.search(text), text


def test_the_card_is_deterministic(findings, ctx, names) -> None:
    finding = findings[0]
    first = build_card(finding, ctx, account_names=names)
    second = build_card(finding, ctx, account_names=names)
    assert first == second


# --- the working is the detector's working ----------------------------------------------


def test_amount_working_matches_an_independent_recomputation(cards, ctx) -> None:
    checked = 0
    accounts = primary_accounts(ctx)
    for finding, card in cards:
        hit = next((h for h in finding.signals if h.kind is SignalKind.AMOUNT_OUTLIER), None)
        if hit is None:
            continue
        group = ctx.vouchers.amount_paise[accounts == hit.evidence["account_code"]]
        assert hit.evidence["entries_compared"] == len(group)
        assert hit.evidence["account_median_paise"] == round(float(group.median()))
        # And the card shows the same figures the detector recorded.
        working = {r.label: r.value for s in card.signals for r in s.working if s.kind == hit.kind}
        assert working["Entries compared"] == f"{len(group):,}"
        checked += 1
    assert checked, "the fixture should contain at least one amount outlier"


def test_account_profile_uses_the_detectors_grouping(findings, ctx) -> None:
    accounts = primary_accounts(ctx)
    for finding in findings[:20]:
        profile = account_profile(ctx, finding.voucher_id)
        assert profile is not None
        group = ctx.vouchers.amount_paise[accounts == profile.account_code]
        assert profile.entries == len(group)
        assert profile.low_paise <= profile.median_paise <= profile.high_paise


def test_similar_entries_are_from_the_same_account_and_never_the_entry_itself(
    findings, ctx
) -> None:
    accounts = primary_accounts(ctx)
    for finding in findings[:30]:
        similar = similar_entries(ctx, finding.voucher_id, set())
        assert len(similar) <= 3
        for entry in similar:
            assert entry.voucher_id != finding.voucher_id
            assert accounts[entry.voucher_id] == accounts[finding.voucher_id]


def test_similar_entries_prefer_the_same_accounts_then_the_nearest_amount(findings, ctx) -> None:
    for finding in findings[:30]:
        similar = similar_entries(ctx, finding.voucher_id, set(), limit=10)
        bases = [entry.basis for entry in similar]
        # "same accounts" entries always come before "same debit account" ones.
        assert bases == sorted(bases, key=lambda b: b != "same accounts")
        target = math.log10(max(int(ctx.vouchers.at[finding.voucher_id, "amount_paise"]), 1))
        for basis in set(bases):
            gaps = [
                abs(math.log10(max(e.amount_paise, 1)) - target)
                for e in similar
                if e.basis == basis
            ]
            assert gaps == sorted(gaps)


# --- evidence: four states, never conflated -------------------------------------------------


def test_approval_below_the_limit_is_not_expected_rather_than_missing(cards) -> None:
    states = {
        item.state
        for finding, card in cards
        for item in card.evidence
        if item.name == "Approval" and not finding.evidence.approval_expected
    }
    assert states == {"not_expected"}


def test_counts_only_include_evidence_that_could_have_existed(cards) -> None:
    for _, card in cards:
        countable = [i for i in card.evidence if i.state in {"present", "missing"}]
        assert card.evidence_expected == len(countable)
        assert card.evidence_present == sum(1 for i in countable if i.state == "present")


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    client = TestClient(create_app(tmp_path / "review.db"))
    response = client.post(
        "/api/auth/signup",
        json={"email": "r@example.com", "name": "Reviewer", "password": "long-enough-pass"},
    )
    assert response.status_code == 200
    return client


def _upload(client: TestClient, frame: pd.DataFrame) -> dict:
    buffer = io.StringIO()
    frame.to_csv(buffer, index=False)
    response = client.post(
        "/api/engagements", files={"file": ("ledger.csv", buffer.getvalue().encode(), "text/csv")}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_a_column_missing_from_the_file_is_not_called_missing_evidence(
    client: TestClient, lines: pd.DataFrame
) -> None:
    """No document column means "cannot be checked", not "the client has no documents"."""
    queue = _upload(client, lines.drop(columns=["document_ref"]))
    engagement = queue["engagement"]["id"]
    voucher = queue["findings"][0]["voucher_id"]

    card = client.get(f"/api/engagements/{engagement}/findings/{voucher}").json()["card"]
    document = next(i for i in card["evidence"] if i["name"] == "Supporting document")
    assert document["state"] == "not_in_file"
    assert "cannot be checked" in document["detail"]


# --- through the API --------------------------------------------------------------------------


def test_the_card_arrives_with_a_single_finding_and_not_with_the_queue(
    client: TestClient, lines: pd.DataFrame
) -> None:
    queue = _upload(client, lines)
    assert all(f["card"] is None for f in queue["findings"])

    engagement = queue["engagement"]["id"]
    voucher = queue["findings"][0]["voucher_id"]
    card = client.get(f"/api/engagements/{engagement}/findings/{voucher}").json()["card"]
    assert card["summary"] and card["signals"] and card["limitation"]
    assert card["profile"]["account_name"], "the profile names the account"


def test_minor_signals_are_not_queue_chips(client: TestClient, lines: pd.DataFrame) -> None:
    queue = _upload(client, lines)
    for finding in queue["findings"]:
        minor = {s["kind"] for s in finding["signals"] if s["minor"]}
        majors = [s["kind"] for s in finding["signals"] if not s["minor"]]
        if majors:
            assert not minor & set(finding["concerns"])
            assert finding["concerns"] == list(dict.fromkeys(majors)), "strongest first"


def test_the_card_survives_a_restart(tmp_path: Path, lines: pd.DataFrame) -> None:
    store = tmp_path / "review.db"
    first = TestClient(create_app(store))
    first.post(
        "/api/auth/signup",
        json={"email": "r@example.com", "name": "Reviewer", "password": "long-enough-pass"},
    )
    queue = _upload(first, lines)
    engagement, voucher = queue["engagement"]["id"], queue["findings"][0]["voucher_id"]
    before = first.get(f"/api/engagements/{engagement}/findings/{voucher}").json()["card"]

    second = TestClient(create_app(store))
    second.post("/api/auth/login", json={"email": "r@example.com", "password": "long-enough-pass"})
    after = second.get(f"/api/engagements/{engagement}/findings/{voucher}").json()["card"]
    assert after == before
