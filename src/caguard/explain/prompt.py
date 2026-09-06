"""Building the prompt, from verified facts and nothing else.

The model never sees a ledger row, a narration, a customer name or anything the
detectors did not already turn into a checked fact. What reaches it is exactly
:meth:`caguard.review.finding.Finding.structured_facts` — which means anything
it says beyond those facts is, by construction, invented, and the guard will
catch it.

The instructions are deliberately narrow. The model is asked to rewrite, not to
assess: it has no information with which to assess, and saying so plainly in the
prompt is cheaper than repairing the output afterwards.
"""

from __future__ import annotations

import json
from typing import Any

from caguard.money import format_inr

SYSTEM_PROMPT = """You write short, plain explanations for a Chartered Accountant
reviewing a ledger.

You will be given verified facts about ONE voucher that software has already
flagged for review. Your only job is to turn those facts into clear prose.

Rules, all of them absolute:
1. Use ONLY the facts given. Never add a number, date, name or account that is
   not in them.
2. Never state or imply that anything is fraud, theft, or wrongdoing of any
   kind. These are observations for a professional to review, nothing more.
3. Never conclude. Do not say anything is proven, certain, or must be the case.
4. Do not recommend an action, an adjustment or a disallowance.
5. Write 3 to 5 sentences of plain British English. No lists, no headings, no
   markdown.
6. Lead with the concern that contributed most.

You are rewriting findings, not making them. The software decided what matters;
you are making it readable."""


def build_prompt(facts: dict[str, Any]) -> str:
    """The user-side prompt for one finding."""
    return (
        "Here are the verified facts about one flagged voucher.\n\n"
        f"{_readable_facts(facts)}\n\n"
        "Write the explanation now, following every rule."
    )


def build_messages(facts: dict[str, Any]) -> list[dict[str, str]]:
    """Chat messages for a provider that expects them."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_prompt(facts)},
    ]


def _readable_facts(facts: dict[str, Any]) -> str:
    """Facts as prose-shaped lines.

    A small model reads labelled lines more reliably than raw JSON, and the
    rupee amount is pre-formatted so it is never asked to divide by 100 — an
    arithmetic slip would read exactly like an invented figure.
    """
    amount = facts.get("amount_paise", 0)
    lines = [
        f"Voucher: {facts.get('voucher_id')}",
        f"Date: {facts.get('voucher_date')}",
        f"Amount: {format_inr(int(amount))}",
        f"Review priority: {facts.get('priority')} ({facts.get('band')})",
        f"Evidence completeness: {facts.get('evidence_completeness')}",
    ]

    missing = facts.get("evidence_missing") or []
    lines.append(
        "Missing from the evidence trail: " + (", ".join(missing) if missing else "nothing")
    )
    lines.append("Ledger lines: " + ", ".join(facts.get("source_lines", [])))
    lines.append("")
    lines.append("Concerns raised, most important first:")

    signals = sorted(facts.get("signals", []), key=lambda s: -float(s.get("contribution", 0.0)))
    for position, signal in enumerate(signals, start=1):
        lines.append(f"  {position}. {signal.get('reason')}")

    return "\n".join(lines)


def facts_as_json(facts: dict[str, Any]) -> str:
    """The same facts as JSON, for providers or logs that prefer it."""
    return json.dumps(facts, indent=2, sort_keys=True, default=str)
