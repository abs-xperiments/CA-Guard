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
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
from pathlib import Path

import httpx
import pandas as pd

from caguard.benchmark.generator import GeneratorConfig, generate

ROOT = Path(__file__).resolve().parent.parent
API = "http://127.0.0.1:8000"
WEB_PORT = int(os.environ.get("SMOKE_WEB_PORT", "3999"))
WEB = f"http://127.0.0.1:{WEB_PORT}"

#: Comfortably past the 10 MB proxy default that used to break uploads.
TARGET_BYTES = 25 * 1024 * 1024


def main() -> int:
    if not (ROOT / "web" / ".next" / "BUILD_ID").exists():
        print("web/ is not built. Run: cd web && npm run build", file=sys.stderr)
        return 2

    for port in (8000, WEB_PORT):
        if _port_in_use(port):
            # A server already on the port would answer instead of the build
            # under test — and every check would quietly test the wrong code.
            print(f"Port {port} is already in use. Stop whatever is running there first.",
                  file=sys.stderr)  # fmt: skip
            return 2

    workdir = Path(tempfile.mkdtemp(prefix="caguard-smoke-"))
    processes: list[subprocess.Popen[bytes]] = []
    try:
        processes.append(_start_api(workdir))
        _wait_for(f"{API}/api/health")
        processes.append(_start_web())
        _wait_for(f"{WEB}/api/health")
        return _run_checks(_large_ledger(workdir))
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            process.wait(timeout=10)
        shutil.rmtree(workdir, ignore_errors=True)


def _run_checks(ledger: Path) -> int:
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}{f' — {detail}' if detail else ''}")
        if not ok:
            failures.append(name)

    with httpx.Client(base_url=WEB, timeout=180) as web:
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
            f"{WEB}/api/auth/login",
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
            f"{WEB}/api/auth/login",
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


def _start_api(workdir: Path) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [sys.executable, "-m", "caguard.cli", "serve", "--port", "8000",
         "--store", str(workdir / "review.db")],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )  # fmt: skip


def _start_web() -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        # The project's own Next binary, not npx: npx can stall resolving the
        # package, and the build under test is the one in web/node_modules.
        [str(ROOT / "web" / "node_modules" / ".bin" / "next"), "start",
         "--port", str(WEB_PORT), "--hostname", "127.0.0.1"],
        cwd=ROOT / "web", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )  # fmt: skip


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        return probe.connect_ex(("127.0.0.1", port)) == 0


def _wait_for(url: str, seconds: float = 60) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=2).status_code == 200:
                return
        except (httpx.HTTPError, urllib.error.URLError):
            pass
        time.sleep(0.5)
    raise RuntimeError(f"{url} did not come up within {seconds:.0f}s")


if __name__ == "__main__":
    sys.exit(main())
