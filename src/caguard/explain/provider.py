"""The provider boundary: how CA-Guard talks to a model, if there is one.

"No provider" is a supported configuration, not an error state. A firm that
installs nothing gets deterministic explanations and a fully working product,
and the calling code cannot tell the difference beyond a label on the output.

Keeping this a protocol means Ollama is one implementation among possible
others, and swapping or removing one changes nothing upstream.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


class ProviderError(RuntimeError):
    """A provider could not produce text. Always recoverable: the caller falls back."""


@runtime_checkable
class ExplanationProvider(Protocol):
    """Anything that can turn a prompt into prose, locally."""

    @property
    def name(self) -> str:
        """Short identifier recorded on the explanation, e.g. ``ollama:qwen3:1.7b``."""
        ...

    def available(self) -> bool:
        """Whether this provider can be used right now, without raising."""
        ...

    def generate(self, messages: list[dict[str, str]], *, timeout: float) -> str:
        """Produce text, or raise :class:`ProviderError`."""
        ...


@dataclass(frozen=True)
class NullProvider:
    """The provider used when no model is installed, or when one is switched off.

    Deliberately not a failure. It reports itself unavailable, the service uses
    the deterministic explanation, and nothing else in the product changes.
    """

    reason: str = "no local model configured"

    @property
    def name(self) -> str:
        return "none"

    def available(self) -> bool:
        return False

    def generate(self, messages: list[dict[str, str]], *, timeout: float) -> str:  # noqa: ARG002
        raise ProviderError(self.reason)


@dataclass
class StubProvider:
    """A scripted provider, for tests and for the comparison harness.

    Lets the whole path — prompt, generation, guard, fallback — be exercised
    before anything is downloaded, which is the order the founder asked for.
    """

    responses: list[str] = field(default_factory=list)
    fail_with: str | None = None
    delay: float = 0.0
    unavailable: bool = False
    calls: list[list[dict[str, str]]] = field(default_factory=list)
    label: str = "stub"

    @property
    def name(self) -> str:
        return f"stub:{self.label}"

    def available(self) -> bool:
        """Present unless told otherwise, so failures during generation are testable."""
        return not self.unavailable

    def generate(self, messages: list[dict[str, str]], *, timeout: float) -> str:
        self.calls.append(messages)
        if self.delay > timeout:
            raise ProviderError(f"stub exceeded the {timeout}s budget")
        if self.fail_with is not None:
            raise ProviderError(self.fail_with)
        if not self.responses:
            raise ProviderError("stub has no scripted responses left")
        return self.responses.pop(0)
