"""End-to-end smoke test through the real workspace, not just the API.

API-level tests talk to FastAPI directly, so they could not see that the Next.js
proxy in front of it truncated every upload above 10 MB. This script runs the
two processes the way the container does — the API on loopback port 8000 (the
address the production build proxies to), the built workspace in front — and
drives them over HTTP:

    uv run python scripts/smoke_workspace.py           # needs `npm run build` in web/

It uses a fresh, temporary review database and synthetic data only, and stops
both processes when it finishes. Exit code 0 means every check passed.
"""

from __future__ import annotations

import io
import os
import sys
import time
from pathlib import Path

import httpx
import pandas as pd
from stack import StackError, running_stack

from caguard.benchmark.generator import GeneratorConfig, generate

ROOT = Path(__file__).resolve().parent.parent
WEB_PORT = int(os.environ.get("SMOKE_WEB_PORT", "3999"))

#: Comfortably past the 10 MB proxy default that used to break uploads.
TARGET_BYTES = 25 * 1024 * 1024


def main() -> int:
    try:
        with running_stack(WEB_PORT) as stack:
            return _run_checks(stack.web, _large_ledger(stack.data_dir))
    except StackError as exc:
        print(exc, file=sys.stderr)
        return 2


def _run_checks(web_url: str, ledger: Path) -> int:
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}{f' — {detail}' if detail else ''}")
        if not ok:
            failures.append(name)

    with httpx.Client(base_url=web_url, timeout=180) as web:
        page = web.get("/login")
        csp = page.headers.get("content-security-policy", "")
        check(
            "workspace pages carry security headers",
            "frame-ancestors 'none'" in csp
            and page.headers.get("x-content-type-options") == "nosniff",
            csp[:60] + "…" if csp else "no CSP header",
        )

        signup = web.post(
            "/api/auth/signup",
            json={"email": "smoke@example.com", "name": "Smoke", "password": "smoke-pass-123"},
        )
        check("sign up through the workspace", signup.status_code == 200, signup.text[:120])

        size_mb = ledger.stat().st_size / 1024 / 1024
        started = time.perf_counter()
        with ledger.open("rb") as handle:
            upload = web.post(
                "/api/engagements", files={"file": ("big-ledger.csv", handle, "text/csv")}
            )
        elapsed = time.perf_counter() - started
        check(
            f"{size_mb:.0f} MB upload through the workspace proxy",
            upload.status_code == 200,
            f"HTTP {upload.status_code} in {elapsed:.1f}s",
        )
        if upload.status_code == 200:
            body = upload.json()
            check(
                "every row of the large ledger was used",
                body["intake"]["rows_read"] == body["intake"]["rows_used"],
                f"{body['intake']['rows_used']:,} rows, {body['flagged']} findings",
            )

        forwarded = httpx.post(
            f"{web_url}/api/auth/login",
            json={"email": "smoke@example.com", "password": "smoke-pass-123"},
            headers={"X-Forwarded-Proto": "https"},
        )
        cookie = forwarded.headers.get("set-cookie", "")
        check(
            "session cookie is Secure when the browser arrived over HTTPS",
            forwarded.status_code == 200 and "secure" in cookie.lower(),
            cookie.split(";")[0][:24] + "…" if cookie else "no cookie",
        )
        plain = httpx.post(
            f"{web_url}/api/auth/login",
            json={"email": "smoke@example.com", "password": "smoke-pass-123"},
        )
        check(
            "plain local http still signs in (cookie not marked Secure)",
            plain.status_code == 200
            and "secure" not in plain.headers.get("set-cookie", "").lower(),
        )

    print(f"\n{'All checks passed.' if not failures else f'{len(failures)} check(s) failed.'}")
    return 1 if failures else 0


def _large_ledger(workdir: Path) -> Path:
    """A synthetic ledger above TARGET_BYTES, built by repeating one generated year."""
    base = generate(GeneratorConfig(seed=9001, n_vouchers=3000)).lines
    one = io.StringIO()
    base.to_csv(one, index=False)
    copies = TARGET_BYTES // len(one.getvalue().encode()) + 1
    frames = [
        base.assign(voucher_id=base.voucher_id + f"-{k}", line_id=base.line_id + f"-{k}")
        for k in range(copies)
    ]
    path = workdir / "big-ledger.csv"
    pd.concat(frames).to_csv(path, index=False)
    return path


if __name__ == "__main__":
    sys.exit(main())
