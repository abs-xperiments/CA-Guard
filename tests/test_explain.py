"""Tests for the explanation layer.

The rule these exist to hold: **the model renders a Finding, it never makes
one.** Detection, scoring and ranking are complete before a token is generated,
and the product works identically with no model installed.

Everything here runs against a stub, so the whole path — prompt, generation,
guard, fallback — is exercised without anything being downloaded.
"""

from __future__ import annotations

import pytest

from caguard.benchmark.generator import GeneratorConfig, generate
from caguard.explain.deterministic import DISCLAIMER, explain_deterministically
from caguard.explain.guard import (
    FORBIDDEN_PHRASES,
    MAX_WORDS,
    check_grounding,
    supported_numbers,
)
from caguard.explain.ollama import (
    DEFAULT_MODEL,
    NotLocalError,
    OllamaProvider,
    require_loopback,
)
from caguard.explain.prompt import SYSTEM_PROMPT, build_messages, build_prompt
from caguard.explain.provider import NullProvider, ProviderError, StubProvider
from caguard.explain.service import ExplanationService, Source
from caguard.review.finding import Finding
from caguard.review.fusion import build_findings


@pytest.fixture(scope="module")
def findings() -> list[Finding]:
    ledger = generate(GeneratorConfig(seed=101, n_vouchers=1000))
    return build_findings(ledger.lines)


@pytest.fixture
def finding(findings: list[Finding]) -> Finding:
    return findings[0]


# --- the deterministic path --------------------------------------------------


def test_deterministic_explanation_reads_as_prose(finding: Finding) -> None:
    text = explain_deterministically(finding)
    assert text.count(".") >= 4
    assert "\n\n" in text
    assert not text.startswith("-")


def test_deterministic_explanation_names_every_concern(finding: Finding) -> None:
    text = explain_deterministically(finding)
    for reason in finding.reasons:
        assert reason in text


def test_deterministic_explanation_states_the_evidence_position(
    finding: Finding,
) -> None:
    assert "evidence trail" in explain_deterministically(finding)


def test_deterministic_explanation_cites_its_source_lines(finding: Finding) -> None:
    text = explain_deterministically(finding)
    for line_id in finding.line_ids:
        assert line_id in text


def test_deterministic_explanation_never_concludes(findings: list[Finding]) -> None:
    """CA-Guard raises observations. The professional reaches the conclusion."""
    for item in findings[:25]:
        lowered = explain_deterministically(item).lower()
        for phrase in FORBIDDEN_PHRASES:
            assert phrase not in lowered, f"{item.voucher_id} used {phrase!r}"


def test_deterministic_explanation_carries_the_disclaimer(finding: Finding) -> None:
    assert DISCLAIMER in explain_deterministically(finding)


def test_deterministic_explanation_passes_its_own_guard(
    findings: list[Finding],
) -> None:
    """The path that always runs must itself be grounded.

    If our own template cannot satisfy the guard, the guard is wrong.
    """
    for item in findings[:25]:
        result = check_grounding(explain_deterministically(item), item.structured_facts())
        assert result.passed, f"{item.voucher_id}: {result.summary()}"


# --- facts and prompt --------------------------------------------------------


def test_facts_carry_every_signal(finding: Finding) -> None:
    facts = finding.structured_facts()
    assert len(facts["signals"]) == len(finding.signals)
    assert facts["source_lines"] == list(finding.line_ids)


def test_prompt_contains_only_facts(finding: Finding) -> None:
    """No ledger rows, no narrations, no customer names reach the model."""
    prompt = build_prompt(finding.structured_facts())
    assert finding.voucher_id in prompt
    for forbidden in ("Sundry", "HDFC", "Pvt Ltd", "narration"):
        assert forbidden not in prompt


def test_prompt_pre_formats_the_amount(finding: Finding) -> None:
    """The model is never asked to divide by 100.

    An arithmetic slip would read exactly like an invented figure.
    """
    assert "₹" in build_prompt(finding.structured_facts())


def test_system_prompt_forbids_conclusions() -> None:
    lowered = SYSTEM_PROMPT.lower()
    assert "never conclude" in lowered
    assert "only the facts given" in lowered


def test_messages_are_system_then_user(finding: Finding) -> None:
    messages = build_messages(finding.structured_facts())
    assert [m["role"] for m in messages] == ["system", "user"]


# --- the guard ---------------------------------------------------------------


def test_guard_accepts_a_faithful_rendering(finding: Finding) -> None:
    facts = finding.structured_facts()
    text = (
        f"Voucher {facts['voucher_id']} is flagged for review. "
        f"{facts['signals'][0]['reason']} "
        "The evidence trail is incomplete."
    )
    assert check_grounding(text, facts).passed


def test_guard_catches_an_invented_number(finding: Finding) -> None:
    facts = finding.structured_facts()
    result = check_grounding("The voucher was posted for ₹9,87,654.32 without support.", facts)
    assert not result.passed
    assert result.unsupported_numbers


@pytest.mark.parametrize("phrase", ["fraudulent", "proves", "must be", "certainly", "illegal"])
def test_guard_catches_conclusive_language(finding: Finding, phrase: str) -> None:
    result = check_grounding(f"This entry {phrase} a problem.", finding.structured_facts())
    assert not result.passed
    assert phrase in result.forbidden_phrases


def test_guard_rejects_empty_text(finding: Finding) -> None:
    assert not check_grounding("   ", finding.structured_facts()).passed


def test_guard_rejects_rambling(finding: Finding) -> None:
    text = "The voucher is flagged for review. " * (MAX_WORDS // 2)
    assert not check_grounding(text, finding.structured_facts()).passed


def test_guard_allows_a_rupee_amount_written_in_rupees(finding: Finding) -> None:
    """A paise fact may legitimately be written as rupees."""
    facts = {"amount_paise": 21245556}
    allowed = supported_numbers(facts)
    assert "212455.56" in allowed
    assert "21245556" in allowed


def test_guard_allows_a_ratio_written_as_a_percentage() -> None:
    allowed = supported_numbers({"evidence_completeness": 0.15})
    assert "15" in allowed


def test_guard_summary_is_readable(finding: Finding) -> None:
    result = check_grounding("It was ₹9,99,999.99 and is fraudulent.", finding.structured_facts())
    assert "numbers not present" in result.summary()
    assert "conclusion" in result.summary()


# --- providers ---------------------------------------------------------------


def test_null_provider_is_a_supported_configuration() -> None:
    provider = NullProvider()
    assert not provider.available()
    assert provider.name == "none"
    with pytest.raises(ProviderError):
        provider.generate([], timeout=1.0)


def test_stub_records_what_it_was_asked(finding: Finding) -> None:
    stub = StubProvider(responses=["Voucher flagged."])
    ExplanationService(stub).explain(finding)
    assert stub.calls
    assert stub.calls[0][0]["role"] == "system"


# --- the service -------------------------------------------------------------


def test_service_uses_the_deterministic_path_with_no_model(finding: Finding) -> None:
    result = ExplanationService().explain(finding)
    assert result.source is Source.DETERMINISTIC
    assert result.text == explain_deterministically(finding)
    assert result.fallback_reason == "no local model available"


def test_service_uses_generated_text_when_it_is_grounded(finding: Finding) -> None:
    facts = finding.structured_facts()
    grounded = f"Voucher {facts['voucher_id']} needs review. {facts['signals'][0]['reason']}"
    result = ExplanationService(StubProvider(responses=[grounded])).explain(finding)
    assert result.source is Source.MODEL
    assert result.guard is not None and result.guard.passed
    assert DISCLAIMER in result.text


def test_service_falls_back_when_the_model_invents_a_number(finding: Finding) -> None:
    stub = StubProvider(responses=["The amount was ₹8,88,888.88 and unsupported."])
    result = ExplanationService(stub).explain(finding)
    assert result.source is Source.DETERMINISTIC
    assert result.guard is not None and not result.guard.passed
    assert "numbers not present" in (result.fallback_reason or "")


def test_service_falls_back_when_the_model_concludes(finding: Finding) -> None:
    stub = StubProvider(responses=["This voucher is fraudulent."])
    result = ExplanationService(stub).explain(finding)
    assert result.source is Source.DETERMINISTIC
    assert "conclusion" in (result.fallback_reason or "")


def test_service_falls_back_when_the_model_errors(finding: Finding) -> None:
    result = ExplanationService(StubProvider(fail_with="model crashed")).explain(finding)
    assert result.source is Source.DETERMINISTIC
    assert result.fallback_reason == "model crashed"


def test_service_falls_back_when_the_model_is_too_slow(finding: Finding) -> None:
    stub = StubProvider(responses=["anything"], delay=99.0)
    result = ExplanationService(stub, timeout=0.5).explain(finding)
    assert result.source is Source.DETERMINISTIC
    assert "budget" in (result.fallback_reason or "")


def test_service_never_alters_the_finding(finding: Finding) -> None:
    """The model explains what was decided. It decides nothing."""
    before = (finding.priority, finding.band, finding.kinds, finding.contributions.copy())
    ExplanationService(StubProvider(responses=["Voucher flagged for review."])).explain(finding)
    after = (finding.priority, finding.band, finding.kinds, finding.contributions)
    assert before == after


def test_every_finding_gets_an_explanation(findings: list[Finding]) -> None:
    """No configuration produces a finding a reviewer cannot read."""
    service = ExplanationService()
    for result in service.explain_all(findings[:20]):
        assert result.text.strip()
        assert result.provenance()


def test_provenance_is_honest(finding: Finding) -> None:
    generated = ExplanationService(
        StubProvider(responses=[f"Voucher {finding.voucher_id} needs review."])
    ).explain(finding)
    assert "checked before display" in generated.provenance()
    assert "CA-Guard" in ExplanationService().explain(finding).provenance()


# --- local only --------------------------------------------------------------


@pytest.mark.parametrize(
    "url", ["http://127.0.0.1:11434", "http://localhost:11434", "http://[::1]:11434"]
)
def test_loopback_addresses_are_accepted(url: str) -> None:
    require_loopback(url)


@pytest.mark.parametrize(
    "url",
    ["http://192.168.1.50:11434", "https://api.example.com", "http://10.0.0.1:11434"],
)
def test_non_loopback_addresses_are_refused(url: str) -> None:
    """Fails closed: a mistyped host must stop the run, not post a ledger elsewhere."""
    with pytest.raises(NotLocalError, match="loopback"):
        require_loopback(url)


def test_ollama_provider_refuses_a_remote_host_at_construction() -> None:
    with pytest.raises(NotLocalError):
        OllamaProvider(host="http://203.0.113.10:11434")


def test_ollama_provider_defaults_to_the_small_model() -> None:
    """8 GB of RAM decides this, not preference."""
    provider = OllamaProvider()
    assert provider.model == DEFAULT_MODEL == "qwen3:1.7b"
    assert provider.name == "ollama:qwen3:1.7b"
    assert provider.temperature == 0.0


def test_ollama_reports_unavailable_rather_than_raising_when_absent() -> None:
    """Nothing installed is an ordinary state, not an error."""
    provider = OllamaProvider(host="http://127.0.0.1:1", model="nope")
    assert provider.available() is False


# --- the comparison harness --------------------------------------------------


def test_quality_scores_the_deterministic_path_perfectly(findings: list[Finding]) -> None:
    """The path that always runs must be beyond reproach on grounding."""
    from caguard.evaluation.explanations import compare_providers, summarise

    frame = compare_providers(findings[:10], {"deterministic": None})
    summary = summarise(frame)
    assert summary.loc["deterministic", "factual_consistency"] == 1.0
    assert summary.loc["deterministic", "unsupported_claims"] == 0.0
    assert summary.loc["deterministic", "evidence_coverage"] == 1.0


def test_a_hallucinating_model_never_reaches_the_reviewer(
    findings: list[Finding],
) -> None:
    """The guard's whole purpose, measured end to end.

    Invented figures and conclusive language must be rejected every time, not
    most of the time — a fabricated number reads exactly like a real one.
    """
    from caguard.evaluation.explanations import compare_providers, summarise

    sample = findings[:10]
    bad = StubProvider(
        responses=["This voucher for Rs 7,45,000.00 is clearly fraudulent and must be reversed."]
        * len(sample),
        label="bad",
    )
    frame = compare_providers(sample, {"hallucinating": bad})
    assert summarise(frame).loc["hallucinating", "model_text_used"] == 0.0
    assert (frame.source == "deterministic").all()


def test_a_faithful_model_is_accepted(findings: list[Finding]) -> None:
    from caguard.evaluation.explanations import compare_providers, summarise

    sample = findings[:5]
    good = StubProvider(
        responses=[f"Voucher {f.voucher_id} is flagged for review. {f.reasons[0]}" for f in sample],
        label="good",
    )
    frame = compare_providers(sample, {"faithful": good})
    assert summarise(frame).loc["faithful", "model_text_used"] == 1.0


def test_readability_note_is_plain_english() -> None:
    from caguard.evaluation.explanations import readability_note

    assert readability_note(12) == "easy"
    assert readability_note(22) == "fair"
    assert readability_note(40) == "heavy"


# --- the memory gate ---------------------------------------------------------


def test_memory_status_reads_the_machine() -> None:
    from caguard.explain.memory import measure

    status = measure()
    assert status.total_gb >= 0
    assert "sufficient" in status.summary()


def test_memory_gate_refuses_a_machine_that_is_swapping() -> None:
    """Downloading onto a swapping machine measures page faults, not inference."""
    from caguard.explain.memory import MemoryStatus

    swapping = MemoryStatus(total_gb=8.0, available_gb=4.0, compressed_gb=2.7, swap_used_gb=6.9)
    assert not swapping.sufficient


def test_memory_gate_refuses_when_there_is_too_little_free() -> None:
    from caguard.explain.memory import MemoryStatus

    tight = MemoryStatus(total_gb=8.0, available_gb=1.4, compressed_gb=2.7, swap_used_gb=0.5)
    assert not tight.sufficient


def test_memory_gate_allows_a_healthy_machine() -> None:
    from caguard.explain.memory import MemoryStatus

    healthy = MemoryStatus(total_gb=16.0, available_gb=8.0, compressed_gb=0.5, swap_used_gb=0.1)
    assert healthy.sufficient


def test_require_headroom_raises_rather_than_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fails closed: the gate stops the download, it does not advise against it."""
    from caguard.explain import memory

    monkeypatch.setattr(memory, "measure", lambda: memory.MemoryStatus(8.0, 0.5, 3.0, 7.0))
    with pytest.raises(memory.InsufficientMemoryError, match="Not enough free memory"):
        memory.require_headroom()


# --- what the real model taught us -------------------------------------------


def test_adapter_disables_reasoning_mode() -> None:
    """Qwen3 reasons before answering unless told not to.

    Measured on an 8 GB machine: reasoning on spent 1,409 characters thinking,
    hit the token cap and returned truncated text — or nothing — in 24.7s. Off:
    a complete answer in 7.4s. There is nothing to reason about; the finding is
    already decided.
    """
    import inspect

    from caguard.explain import ollama

    source = inspect.getsource(ollama.OllamaProvider.generate)
    assert '"think": False' in source


def test_adapter_reports_a_reasoning_only_response_clearly() -> None:
    """A model that spends its whole budget thinking must fail loudly, not blankly."""
    import json
    from unittest.mock import patch

    from caguard.explain.ollama import OllamaProvider

    provider = OllamaProvider()
    reply = {"message": {"content": "", "thinking": "hmm, let me consider..."}}
    with (
        patch.object(provider, "_request", return_value=json.loads(json.dumps(reply))),
        pytest.raises(ProviderError, match="only reasoning"),
    ):
        provider.generate([], timeout=5.0)


def test_prompt_insists_on_covering_every_concern() -> None:
    """Coverage was the model's one measured weakness, and the prompt fixed it.

    Instruction: fix the prompt before reaching for a larger model. Tightening
    this took coverage from 0.858 to 0.925 while making the text shorter and
    faster.
    """
    assert "EVERY concern" in SYSTEM_PROMPT
    assert "Do not leave any out" in SYSTEM_PROMPT


def test_application_works_with_the_model_switched_off(findings: list[Finding]) -> None:
    """The hard requirement, asserted after a real model was installed.

    Installing one must not have made it a dependency.
    """
    service = ExplanationService(NullProvider())
    for finding in findings[:5]:
        result = service.explain(finding)
        assert result.text.strip()
        assert result.source is Source.DETERMINISTIC
        assert result.latency_seconds == 0.0
