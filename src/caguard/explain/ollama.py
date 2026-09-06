"""Talking to a locally running Ollama instance.

**Loopback only, enforced.** The strongest claim this project makes is that
client financial data never leaves the machine. A mistyped host would quietly
post a ledger to somebody else's server, so a non-loopback address is rejected
when the adapter is constructed rather than when it is used — the failure
happens at configuration time, in front of whoever made the mistake.

Nothing here downloads or installs a model. If Ollama is not running, or the
model is not present, :meth:`available` returns ``False`` and the service uses
the deterministic explanation.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlparse

from caguard.explain.provider import ProviderError

DEFAULT_HOST = "http://127.0.0.1:11434"

#: The first real model, chosen for an 8 GB machine. Q4_K_M is Ollama's default
#: quantisation for this tag: roughly 1.4 GB resident.
DEFAULT_MODEL = "qwen3:1.7b"

#: Hostnames that resolve to this machine.
LOOPBACK_NAMES = frozenset({"localhost", "ip6-localhost"})


class NotLocalError(ValueError):
    """Raised when a host is not on this machine. Never downgraded to a warning."""


@dataclass
class OllamaProvider:
    """A local Ollama server. Constructing one does not contact it."""

    host: str = DEFAULT_HOST
    model: str = DEFAULT_MODEL
    temperature: float = 0.0  # deterministic: the same finding reads the same way

    def __post_init__(self) -> None:
        require_loopback(self.host)

    @property
    def name(self) -> str:
        return f"ollama:{self.model}"

    def available(self) -> bool:
        """Whether Ollama is running here and has the model. Never raises."""
        try:
            return self.model in self.installed_models()
        except ProviderError:
            return False

    def installed_models(self) -> list[str]:
        """Model tags this Ollama instance already has."""
        payload = self._request("/api/tags", None, timeout=2.0)
        return [str(entry.get("name", "")) for entry in payload.get("models", [])]

    def generate(self, messages: list[dict[str, str]], *, timeout: float) -> str:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "seed": 20250906,
                "num_predict": 400,
            },
        }
        payload = self._request("/api/chat", body, timeout=timeout)
        content = payload.get("message", {}).get("content", "")
        if not str(content).strip():
            raise ProviderError("the model returned nothing")
        return _strip_reasoning(str(content))

    def _request(self, path: str, body: dict[str, Any] | None, *, timeout: float) -> dict[str, Any]:
        url = f"{self.host.rstrip('/')}{path}"
        require_loopback(url)
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode())
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProviderError(f"could not reach Ollama at {self.host}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise ProviderError(f"Ollama returned malformed JSON: {exc}") from exc


def require_loopback(url: str) -> None:
    """Reject any address that is not on this machine.

    Fails closed. A configuration mistake must stop the run, not quietly send a
    client's ledger somewhere else.
    """
    host = urlparse(url).hostname
    if host is None:
        raise NotLocalError(f"cannot determine the host in {url!r}")
    if host in LOOPBACK_NAMES:
        return
    try:
        if ip_address(host).is_loopback:
            return
    except ValueError as exc:
        raise NotLocalError(
            f"{host!r} is not a loopback address. CA-Guard only talks to a model "
            "running on this machine; client data must not leave it."
        ) from exc
    raise NotLocalError(
        f"{host!r} is not a loopback address. CA-Guard only talks to a model "
        "running on this machine; client data must not leave it."
    )


def _strip_reasoning(text: str) -> str:
    """Remove a reasoning block if the model emitted one.

    Qwen3 can wrap private reasoning in ``<think>`` tags. That is working
    material, not the explanation, and it must never reach a reviewer.
    """
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    return text.strip()
