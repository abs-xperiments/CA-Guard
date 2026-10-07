"""Security properties that must hold on every run, not once at review time.

Three things this project promises and therefore has to prove:

1. **No secret is ever committed.** The repository is intended to be public.
2. **Analysing a ledger needs no network.** That is the privacy claim in its
   entirety — a code path that quietly reaches out would break it without anyone
   noticing.
3. **Uploads cannot escape their directory.** A filename is untrusted input.
"""

from __future__ import annotations

import re
import socket
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: Files we scan. Lock files and vendored code are excluded because they contain
#: hashes that look like keys and are not ours to police.
SCANNED_SUFFIXES = frozenset({".py", ".ts", ".tsx", ".toml", ".md", ".yaml", ".yml", ".sh"})
SKIP_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "node_modules",
        ".next",
        "__pycache__",
        ".ruff_cache",
        ".pytest_cache",
        "data",
    }
)

#: Patterns that indicate a real credential rather than the word "key".
SECRET_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"AKIA[0-9A-Z]{16}", "an AWS access key id"),
    (r"sk-[A-Za-z0-9]{32,}", "an OpenAI-style secret key"),
    (r"ghp_[A-Za-z0-9]{36}", "a GitHub personal access token"),
    (r"xox[baprs]-[A-Za-z0-9-]{10,}", "a Slack token"),
    (r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", "a private key"),
    (r"postgres(?:ql)?://[^\s:]+:[^\s@]{6,}@", "a database URL with a password"),
    (
        r"(?i)\b(?:api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"\s]{16,}['\"]",
        "a hard-coded credential",
    ),
)


def scanned_files() -> list[Path]:
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path.suffix in SCANNED_SUFFIXES
        and not SKIP_DIRS & set(path.relative_to(ROOT).parts)
    ]


def test_there_are_files_to_scan() -> None:
    """Guards the guard: an empty scan would pass vacuously."""
    assert len(scanned_files()) > 40


def test_no_secrets_are_committed() -> None:
    """The repository is meant to be public. A leaked key cannot be un-leaked."""
    found: list[str] = []
    for path in scanned_files():
        if path.name == "test_security.py":
            continue  # this file necessarily contains the patterns
        text = path.read_text(errors="ignore")
        for pattern, description in SECRET_PATTERNS:
            if re.search(pattern, text):
                found.append(f"{path.relative_to(ROOT)}: looks like {description}")
    assert not found, "possible secrets committed:\n  " + "\n  ".join(found)


def test_env_files_are_ignored() -> None:
    ignore = (ROOT / ".gitignore").read_text()
    assert ".env" in ignore
    assert "data/review.db" in ignore, "a firm's decisions must not be committed"


def test_no_database_is_committed() -> None:
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=False
    ).stdout.splitlines()
    offenders = [name for name in tracked if name.endswith((".db", ".sqlite", ".sqlite3"))]
    assert not offenders, f"a database is committed: {offenders}"


# --- the privacy claim, proven ------------------------------------------------


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any outbound connection raise, so a hidden one cannot pass unnoticed."""

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError(
            "the analysis opened a network connection; ledger data must not leave the machine"
        )

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def test_analysis_needs_no_network(no_network: None) -> None:
    """The whole privacy claim in one test.

    Generation, detection, fusion and explanation must all complete with every
    socket call raising.
    """
    from caguard.benchmark.generator import GeneratorConfig, generate
    from caguard.explain.service import ExplanationService
    from caguard.review.fusion import build_findings

    ledger = generate(GeneratorConfig(seed=101, n_vouchers=300))
    findings = build_findings(ledger.lines)
    assert findings

    explanation = ExplanationService().explain(findings[0])
    assert explanation.text.strip()
    assert explanation.source.value == "deterministic"


def test_intake_needs_no_network(no_network: None, tmp_path: Path) -> None:
    from caguard.benchmark.generator import GeneratorConfig, generate
    from caguard.intake.normalise import normalise
    from caguard.intake.readers import read_table

    path = tmp_path / "ledger.csv"
    generate(GeneratorConfig(seed=102, n_vouchers=200)).lines.to_csv(path, index=False)
    assert not normalise(read_table(path)).lines.empty


# --- untrusted input ----------------------------------------------------------


@pytest.mark.parametrize(
    "filename",
    ["../../etc/passwd", "..\\..\\windows\\system32", "/etc/shadow", "ledger.csv.exe"],
)
def test_upload_filenames_cannot_escape_their_directory(filename: str) -> None:
    """A filename is untrusted input, and Path.suffix does not sanitise it.

    On POSIX ``Path("..\\..\\windows\\x").suffix`` is ``".\\windows\\x"``,
    because a backslash is not a separator there. Putting that into a temporary
    filename would traverse on Windows, so the suffix is matched against an
    allowlist instead of trusted.
    """
    from caguard.intake.readers import safe_suffix

    suffix = safe_suffix(filename)
    assert "/" not in suffix
    assert "\\" not in suffix
    assert ".." not in suffix


def test_uploads_are_size_limited() -> None:
    from caguard.api.app import MAX_UPLOAD_BYTES
    from caguard.intake.readers import MAX_ROWS
    from caguard.intake.readers import MAX_UPLOAD_BYTES as READER_LIMIT

    assert 0 < MAX_UPLOAD_BYTES <= 500 * 1024 * 1024
    assert 0 < READER_LIMIT <= 500 * 1024 * 1024
    assert 0 < MAX_ROWS <= 10_000_000


def test_the_api_and_the_model_share_one_loopback_rule() -> None:
    """Two places could expose a ledger; both must use the same check."""
    from caguard.explain.ollama import NotLocalError, require_loopback

    require_loopback("http://127.0.0.1:8000", purpose="serve the workspace")
    with pytest.raises(NotLocalError):
        require_loopback("http://0.0.0.0:8000", purpose="serve the workspace")


def test_sql_is_parameterised() -> None:
    """Never interpolate a value into SQL. Checked by reading the source."""
    store = (ROOT / "src" / "caguard" / "review" / "store.py").read_text()
    for line in store.splitlines():
        stripped = line.strip()
        if any(word in stripped.upper() for word in ("SELECT ", "INSERT ", "DELETE ")):
            assert 'f"' not in stripped and "format(" not in stripped, (
                f"SQL built by string formatting: {stripped}"
            )


# --- the self-hosted image ----------------------------------------------------


def test_docker_files_reference_what_exists() -> None:
    """A compose file that names a missing script fails at the worst moment."""
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert (ROOT / "docker" / "entrypoint.sh").is_file()
    assert (ROOT / "compose.yaml").is_file()
    assert 'output: "standalone"' in (ROOT / "web" / "next.config.ts").read_text(), (
        "the image copies .next/standalone, which Next only produces on request"
    )
    # The image starts as root only so the entrypoint can hand platform volumes
    # (mounted root-owned on Railway) to the app user; the application itself
    # must never run as root. Enforced in the entrypoint, checked here.
    assert "useradd --create-home --uid 10001 caguard" in dockerfile


def test_the_application_never_runs_as_root() -> None:
    """Root is used for one job — owning /data — then dropped for good, capabilities and all.

    Verified at runtime too (docs/deploy.md): every process uid 10001, CapEff 0.
    """
    entrypoint = (ROOT / "docker" / "entrypoint.sh").read_text()
    drop = entrypoint.index("exec setpriv --reuid=caguard --regid=caguard")
    assert "--inh-caps=-all" in entrypoint and "--bounding-set=-all" in entrypoint
    root_block = entrypoint[entrypoint.index('if [ "$(id -u)" = "0" ]') : drop]
    # The only things done as root: create /data and give it to the app user.
    commands = [
        line.strip()
        for line in root_block.splitlines()[1:]
        if line.strip() and not line.strip().startswith("#")
    ]
    assert commands == [
        "mkdir -p /data",
        "find /data -xdev ! -user caguard -exec chown caguard:caguard {} +",
    ], commands
    assert drop < entrypoint.index("python -m caguard.cli serve"), "drop privileges before starting"
    assert drop < entrypoint.index("node web/server.js")


def test_the_container_does_not_publish_the_api() -> None:
    """Only the workspace is reachable; the ledger endpoints stay on loopback."""
    compose = (ROOT / "compose.yaml").read_text()
    assert "127.0.0.1:3000:3000" in compose
    assert "8000:8000" not in compose, "the API must not be published"


def test_the_entrypoint_binds_the_api_to_loopback() -> None:
    entrypoint = (ROOT / "docker" / "entrypoint.sh").read_text()
    assert "--host 127.0.0.1" in entrypoint
    assert "0.0.0.0" not in entrypoint.replace("HOSTNAME=0.0.0.0", "")


def test_the_image_defaults_to_no_model() -> None:
    """A firm installing CA-Guard gets a working product with nothing else."""
    assert "CAGUARD_MODEL: ${CAGUARD_MODEL:-none}" in (ROOT / "compose.yaml").read_text()
    assert "CAGUARD_MODEL=none" in (ROOT / "Dockerfile").read_text()


# --- the hosted demo must say what it is --------------------------------------


def test_demo_mode_is_off_unless_asked_for(tmp_path: Path) -> None:
    """A self-hosted install must never show a demonstration warning."""
    from fastapi.testclient import TestClient

    from caguard.api.app import create_app

    client = TestClient(create_app(tmp_path / "review.db"))
    assert client.get("/api/health").json()["demo_mode"] is False


def test_demo_mode_is_reported_when_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-005: the hosted demo is not the private product and must say so.

    A CA who uploaded a real ledger to a public demo because the interface did
    not say otherwise would have been misled by us.
    """
    from fastapi.testclient import TestClient

    from caguard.api.app import create_app

    monkeypatch.setenv("CAGUARD_DEMO", "1")
    client = TestClient(create_app(tmp_path / "review.db"))
    assert client.get("/api/health").json()["demo_mode"] is True


def test_the_railway_config_health_checks_a_public_endpoint() -> None:
    """The health check must not need credentials, or the deploy never goes live."""
    import json

    config = json.loads((ROOT / "railway.json").read_text())
    assert config["deploy"]["healthcheckPath"] == "/api/health"
    assert config["build"]["builder"] == "DOCKERFILE"
