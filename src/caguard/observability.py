"""What CA-Guard records about itself — and, by construction, nothing about a client.

An operator needs to know that an analysis started, how long it took, how many
rows and findings it produced, and why it failed. They never need a narration,
an account name, an amount, or the name of the client's file — and a log file
that held those would quietly become a second copy of the ledger, outside every
control the product puts around the first.

So events go through one function that accepts only numbers, flags and
identifier-shaped strings. Free text is replaced with ``[redacted]`` here,
rather than trusting every caller to remember. A test runs the whole review
path and checks that no ledger text reaches the log.
"""

from __future__ import annotations

import logging
import re
import sys

#: Identifier-shaped: hex ids, voucher numbers, enum codes, model tags. Spaces,
#: and most punctuation a sentence or a filename would carry, are not allowed.
_SAFE_TEXT = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")

REDACTED = "[redacted]"

_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging(level: int = logging.INFO) -> None:
    """Send CA-Guard's events to stderr, where a container's logs are collected."""
    logger = logging.getLogger("caguard")
    if any(getattr(h, "_caguard", False) for h in logger.handlers):
        return  # idempotent: the API may be built more than once in a process
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt="%Y-%m-%dT%H:%M:%S%z"))
    handler._caguard = True  # type: ignore[attr-defined]
    logger.addHandler(handler)
    logger.setLevel(level)


def event(
    logger: logging.Logger, name: str, level: int = logging.INFO, /, **fields: object
) -> None:
    """Log one event as ``name key=value ...``, keeping only safe values.

    ``level`` is positional-only so that no field — whatever it is called —
    can be mistaken for it.
    """
    parts = [name, *(f"{key}={_safe(value)}" for key, value in fields.items())]
    logger.log(level, " ".join(parts))


def _safe(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.3f}"
    text = str(value)
    return text if _SAFE_TEXT.match(text) else REDACTED
