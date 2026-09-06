"""Whether this machine can actually run a local model right now.

Phase 5 was built on a laptop with 8 GB of memory, most of it already spoken
for. Downloading a model onto a machine that is swapping does not produce a slow
product — it produces a **meaningless measurement**, because the latency figure
would be page faults rather than inference, and an unusable machine while it
runs.

So the check is a gate, not a warning. It is cheap, it uses no dependencies
beyond the standard library, and it fails closed.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass

#: Qwen3 1.7B Q4_K_M is roughly 1.4 GB resident, plus context and the runtime.
REQUIRED_GB = 2.5


class InsufficientMemoryError(RuntimeError):
    """Raised instead of downloading onto a machine that cannot run the model."""


@dataclass(frozen=True)
class MemoryStatus:
    """What the machine has spare, right now."""

    total_gb: float
    available_gb: float
    compressed_gb: float
    swap_used_gb: float

    @property
    def sufficient(self) -> bool:
        # Heavy swap means the "available" figure is already borrowed.
        return self.available_gb >= REQUIRED_GB and self.swap_used_gb < self.total_gb * 0.75

    def summary(self) -> str:
        verdict = "sufficient" if self.sufficient else "NOT sufficient"
        return (
            f"total {self.total_gb:.1f} GB · available ~{self.available_gb:.2f} GB · "
            f"compressed {self.compressed_gb:.2f} GB · swap in use "
            f"{self.swap_used_gb:.2f} GB — {verdict} "
            f"(a local model needs about {REQUIRED_GB} GB)"
        )


def measure() -> MemoryStatus:
    """Read current memory pressure. Returns zeros rather than raising off-platform."""
    try:
        vm = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=5).stdout
        total_bytes = int(
            subprocess.run(
                ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5
            ).stdout.strip()
        )
        swap = subprocess.run(
            ["sysctl", "-n", "vm.swapusage"], capture_output=True, text=True, timeout=5
        ).stdout
    except (OSError, subprocess.SubprocessError, ValueError):
        return MemoryStatus(0.0, 0.0, 0.0, 0.0)

    page_match = re.search(r"page size of (\d+)", vm)
    page = int(page_match.group(1)) if page_match else 4096
    pages = {
        m.group(1).strip(): int(m.group(2)) for m in re.finditer(r'"?([A-Za-z ]+?)"?:\s+(\d+)', vm)
    }

    def gb(name: str) -> float:
        return pages.get(name, 0) * page / 1024**3

    reclaimable = (
        gb("Pages free") + gb("Pages inactive") + gb("Pages speculative") + gb("Pages purgeable")
    )
    swap_match = re.search(r"used\s*=\s*([\d.]+)M", swap)
    swap_used = float(swap_match.group(1)) / 1024 if swap_match else 0.0

    return MemoryStatus(
        total_gb=total_bytes / 1024**3,
        available_gb=reclaimable,
        compressed_gb=gb("Pages occupied by compressor"),
        swap_used_gb=swap_used,
    )


def report() -> str:
    return measure().summary()


def require_headroom() -> MemoryStatus:
    """Refuse to proceed unless the machine can genuinely host a model."""
    status = measure()
    if not status.sufficient:
        raise InsufficientMemoryError(
            f"Not enough free memory to run a local model.\n  {status.summary()}\n\n"
            "Close some applications and try again. CA-Guard works fully without "
            "a model — this only affects generated prose."
        )
    return status
