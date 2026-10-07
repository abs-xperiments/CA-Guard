"""Run the API and the built workspace together, as the container does.

Shared by ``scripts/smoke_workspace.py`` and the browser tests in
``tests/e2e``. The API listens on loopback port 8000 — the address the
production build proxies to — and the workspace in front of it. Each run gets
a fresh, temporary data directory, and both processes are stopped afterwards.

It refuses to start if either port is already taken: a server left running
from earlier would answer instead of the build under test, and every check
would quietly test the wrong code. That happened once; it is why this exists.
"""

from __future__ import annotations

import shutil
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
API_PORT = 8000


class StackError(RuntimeError):
    """The stack could not be started in a state worth testing."""


@dataclass(frozen=True)
class Stack:
    web: str
    api: str
    data_dir: Path


@contextmanager
def running_stack(web_port: int = 3999) -> Iterator[Stack]:
    if not (ROOT / "web" / ".next" / "BUILD_ID").exists():
        raise StackError("web/ is not built. Run: cd web && npm run build")
    for port in (API_PORT, web_port):
        if port_in_use(port):
            raise StackError(f"Port {port} is already in use. Stop whatever is running there.")

    data_dir = Path(tempfile.mkdtemp(prefix="caguard-stack-"))
    api = f"http://127.0.0.1:{API_PORT}"
    web = f"http://127.0.0.1:{web_port}"
    processes: list[subprocess.Popen[bytes]] = []
    try:
        processes.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "caguard.cli",
                    "serve",
                    "--port",
                    str(API_PORT),
                    "--store",
                    str(data_dir / "review.db"),
                ],
                cwd=ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        )
        wait_for(f"{api}/api/health")
        # The project's own Next binary, not npx: npx can stall resolving the
        # package, and the build under test is the one in web/node_modules.
        processes.append(
            subprocess.Popen(
                [
                    str(ROOT / "web" / "node_modules" / ".bin" / "next"),
                    "start",
                    "--port",
                    str(web_port),
                    "--hostname",
                    "127.0.0.1",
                ],
                cwd=ROOT / "web",
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        )
        wait_for(f"{web}/api/health")
        yield Stack(web=web, api=api, data_dir=data_dir)
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        shutil.rmtree(data_dir, ignore_errors=True)


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        return probe.connect_ex(("127.0.0.1", port)) == 0


def wait_for(url: str, seconds: float = 60) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise StackError(f"{url} did not come up within {seconds:.0f}s")
