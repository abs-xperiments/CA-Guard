"""Checking generated text against the facts it was supposed to render.

The guard is the reason a model is allowed near this product at all. It reads
the output and asks two questions:

1. **Is every number in this text traceable to the finding?** A figure the model
   invented is the most dangerous kind of error, because it looks exactly like a
   figure it did not invent.
2. **Does it stop short of a conclusion?** CA-Guard raises observations. Words
   like "fraudulent", "proves" or "must be" claim something the software is not
   entitled to claim, whatever the numbers say.

A failure is not a warning. The service discards the text and shows the
deterministic explanation instead — the model does not get a second chance to
be believed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from caguard.explain.vocabulary import VOCABULARY, is_minor, mentions

#: Language that asserts a conclusion CA-Guard is not entitled to reach.
#: Matched on word boundaries so "proven" is caught and "approval" is not.
FORBIDDEN_PHRASES: tuple[str, ...] = (
    "fraud",
    "fraudulent",
    "fraudulently",
    "embezzle",
    "embezzlement",
    "criminal",
    "illegal",
    "unlawful",
    "guilty",
    "theft",
    "stolen",
    "money laundering",
    "laundering",
    "proves",
    "proven",
    "conclusive",
    "conclusively",
    "certainly",
    "definitely",
    "undoubtedly",
    "without doubt",
    "clearly shows",
    "must be",
    "is evidence of",
    "confirms that",
    "we conclude",
    "should be prosecuted",
    "misappropriation",
)

#: A generated explanation longer than this is rambling, whatever it says.
MAX_WORDS = 220

#: Numbers appearing in ordinary prose that need no support from the facts.
#: Deliberately tiny — anything larger must be traceable.
ALWAYS_ALLOWED: frozenset[str] = frozenset({"0", "1", "2", "100"})

_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


@dataclass(frozen=True)
class GuardResult:
    """Whether generated text may be shown, and why not if it may not."""

    passed: bool
    unsupported_numbers: tuple[str, ...] = ()
    forbidden_phrases: tuple[str, ...] = ()
    notes: tuple[str, ...] = field(default_factory=tuple)
    omitted_concerns: tuple[str, ...] = ()

    @property
    def violations(self) -> tuple[str, ...]:
        found: list[str] = []
        if self.unsupported_numbers:
            found.append(
                "numbers not present in the finding: " + ", ".join(self.unsupported_numbers)
            )
        if self.forbidden_phrases:
            found.append("language asserting a conclusion: " + ", ".join(self.forbidden_phrases))
        if self.omitted_concerns:
            found.append("concerns left out: " + ", ".join(self.omitted_concerns))
        found.extend(self.notes)
        return tuple(found)

    def summary(self) -> str:
        return "grounded" if self.passed else "; ".join(self.violations)


def check_grounding(text: str, facts: dict[str, Any]) -> GuardResult:
    """Check that ``text`` says nothing ``facts`` does not support."""
    stripped = text.strip()
    notes: list[str] = []

    if not stripped:
        return GuardResult(False, notes=("the explanation is empty",))
    if len(stripped.split()) > MAX_WORDS:
        notes.append(f"longer than {MAX_WORDS} words")

    allowed = supported_numbers(facts)
    unsupported = tuple(
        sorted({token for token in _NUMBER.findall(stripped) if _normalise(token) not in allowed})
    )

    lowered = stripped.lower()
    forbidden = tuple(phrase for phrase in FORBIDDEN_PHRASES if _mentions(lowered, phrase))
    omitted = omitted_concerns(stripped, facts)

    return GuardResult(
        passed=not unsupported and not forbidden and not notes and not omitted,
        unsupported_numbers=unsupported,
        forbidden_phrases=forbidden,
        notes=tuple(notes),
        omitted_concerns=omitted,
    )


def omitted_concerns(text: str, facts: dict[str, Any]) -> tuple[str, ...]:
    """Concerns the text never mentions.

    A reviewer acts on what they read; a concern the prose drops is invisible to
    them. Minor signals (below the display floor) are exempt — they are "also
    noted" on the card and need not lead the prose.
    """
    missing: list[str] = []
    for signal in facts.get("signals", []):
        kind = str(signal.get("kind", ""))
        if kind not in {k.value for k in VOCABULARY}:
            continue
        if is_minor(float(signal.get("contribution", 0.0))):
            continue
        if not mentions(text, kind):
            missing.append(kind)
    return tuple(sorted(set(missing)))


def supported_numbers(facts: dict[str, Any]) -> set[str]:
    """Every numeric form the facts justify a text using.

    Generous about *representation* and strict about *provenance*: a rupee
    amount may legitimately appear as paise, as rupees, with or without grouping,
    and a date may be split into its parts — but the underlying value has to be
    in the finding.
    """
    allowed: set[str] = set(ALWAYS_ALLOWED)
    for value in _walk(facts):
        allowed |= _representations(value)
    return allowed


def _walk(value: Any) -> list[Any]:
    """Every leaf value in a nested structure of dicts and lists."""
    if isinstance(value, dict):
        return [leaf for item in value.values() for leaf in _walk(item)]
    if isinstance(value, (list, tuple, set)):
        return [leaf for item in value for leaf in _walk(item)]
    return [value]


def _representations(value: Any) -> set[str]:
    """The numeric strings a single fact makes legitimate."""
    forms: set[str] = set()

    if isinstance(value, bool):
        return forms

    if isinstance(value, (int, float, Decimal)):
        number = Decimal(str(value))
        forms |= {_normalise(str(number))}
        # Displaying 0.986722 as 0.99 is faithful rendering, not invention.
        # Rounding is how a number is written for a reader, so every sensible
        # precision is supported by the underlying fact.
        for places in (0, 1, 2, 3):
            forms.add(_normalise(str(round(number, places))))
        # A paise amount may reasonably be written in rupees, rounded or not.
        if isinstance(value, int) and abs(value) >= 100:
            rupees = Decimal(value) / 100
            forms |= {_normalise(str(rupees)), _normalise(str(int(rupees)))}
        # A ratio may reasonably be written as a percentage.
        if isinstance(value, float) and 0.0 <= value <= 1.0:
            percent = Decimal(str(value)) * 100
            forms |= {_normalise(str(round(percent, places))) for places in (0, 1, 2)}
        return forms

    if isinstance(value, str):
        for token in _NUMBER.findall(value):
            forms.add(_normalise(token))
        # Dates: every component, and the day-month-year the UI prefers.
        for part in re.split(r"[-/ :]", value):
            if part.isdigit():
                forms.add(_normalise(part))
                forms.add(_normalise(part.lstrip("0") or "0"))
    return forms


def _normalise(token: str) -> str:
    """Compare numbers by value, not by how they were typed."""
    cleaned = token.replace(",", "").strip()
    try:
        number = Decimal(cleaned)
    except (ArithmeticError, ValueError):
        return cleaned
    normalised = number.normalize()
    text = format(normalised, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _mentions(lowered: str, phrase: str) -> bool:
    return re.search(rf"\b{re.escape(phrase)}\b", lowered) is not None
