"""Enforces ADR-0003 rule 1: the generator and the detectors are separate powers.

If any module outside ``caguard.benchmark`` could import it, a detector could
reach the planted ground truth or reuse the generator's own thresholds, and
every metric the project publishes would be circular. Prose in an ADR does not
prevent that; a failing test does.

This test is expected to grow in importance as Phase 2 adds detectors. It is
written now, before there is anything to catch, precisely so it is already in
place when there is.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "caguard"
BENCHMARK_PACKAGE = "caguard.benchmark"

#: Detection code. Nothing here may reach the generator, under any justification.
#: This is the half of the rule that actually protects the research: a detector
#: that could read the generator's constants or its answer key would be scored
#: against knowledge it will not have on a real client ledger.
DETECT_PACKAGE = SRC / "detect"

#: Everywhere else, a tiny allowlist with stated reasons. Tool entry points
#: legitimately need to invoke the generator; detectors never do.
ALLOWED_IMPORTERS: dict[str, str] = {
    "cli.py": "the `caguard generate` command must be able to invoke the generator",
    "benchmark.py": (
        "the evaluation runner exists to compare predictions against planted "
        "truth; that comparison is its entire job. It reads the ground truth and "
        "never influences a detector, which is the distinction rule 1 protects."
    ),
}
MAX_ALLOWED = 3


def _modules_outside_benchmark() -> list[Path]:
    return sorted(
        path
        for path in SRC.rglob("*.py")
        if "benchmark" not in path.relative_to(SRC).parts and path.name not in ALLOWED_IMPORTERS
    )


def _imported_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


def test_source_tree_is_not_empty() -> None:
    """Guards the guard: an empty scan would pass vacuously."""
    assert _modules_outside_benchmark()


def _detect_modules() -> list[Path]:
    return sorted(DETECT_PACKAGE.rglob("*.py")) if DETECT_PACKAGE.is_dir() else []


@pytest.mark.parametrize("module", _detect_modules(), ids=lambda p: f"detect/{p.stem}")
def test_detectors_can_never_reach_the_generator(module: Path) -> None:
    """The strict half of ADR-0003 rule 1: no exception exists for a detector.

    Anything under ``caguard/detect`` must work from the uploaded ledger alone.
    Reaching into the benchmark would let a detector score against how the data
    was planted rather than what the data shows.
    """
    tree = ast.parse(module.read_text(), filename=str(module))
    offenders = {n for n in _imported_names(tree) if n.startswith(BENCHMARK_PACKAGE)}
    assert not offenders, (
        f"detect/{module.name} imports {sorted(offenders)}. Detection code must "
        "derive everything from the ledger in front of it; there is no allowlist here."
    )


def test_detect_package_is_covered_once_it_exists() -> None:
    """Fails loudly if the package is renamed and the strict rule silently stops applying."""
    if (SRC / "runner.py").exists() or (SRC / "rules.py").exists():
        pytest.fail("detection modules found outside caguard/detect; strict rule would not apply")


def test_the_exception_list_stays_small() -> None:
    """An allowlist that grows quietly is the same as having no rule at all."""
    assert len(ALLOWED_IMPORTERS) <= MAX_ALLOWED, (
        "Too many modules are exempt from ADR-0003 rule 1. Each entry must be a "
        "tool entry point with a stated reason, never a detector."
    )
    assert all(reason for reason in ALLOWED_IMPORTERS.values())


def test_allowed_importers_still_exist() -> None:
    """A stale exemption would silently widen the rule."""
    for name in ALLOWED_IMPORTERS:
        matches = [
            path for path in SRC.rglob(name) if "benchmark" not in path.relative_to(SRC).parts
        ]
        assert matches, f"{name} is exempted but no longer exists"
        assert len(matches) == 1, (
            f"{name} exists in more than one place, so the exemption is ambiguous: "
            f"{[str(m.relative_to(SRC)) for m in matches]}"
        )


@pytest.mark.parametrize("module", _modules_outside_benchmark(), ids=lambda p: p.stem)
def test_no_module_outside_benchmark_imports_it(module: Path) -> None:
    tree = ast.parse(module.read_text(), filename=str(module))
    offenders = {name for name in _imported_names(tree) if name.startswith(BENCHMARK_PACKAGE)}
    assert not offenders, (
        f"{module.relative_to(SRC)} imports {sorted(offenders)}. "
        "ADR-0003 rule 1: detectors must not be able to see the generator or its "
        "ground truth, or every published metric becomes circular."
    )


def test_ground_truth_is_written_to_a_separate_file(tmp_path: Path) -> None:
    """The separation is visible on disk, not merely asserted in prose."""
    from caguard.benchmark.generator import GeneratorConfig, generate

    result = generate(GeneratorConfig(n_vouchers=250))
    ledger_path, truth_path = tmp_path / "l.parquet", tmp_path / "l.truth.json"
    result.lines.to_parquet(ledger_path, index=False)
    result.truth.write(truth_path)

    import pandas as pd

    reloaded = pd.read_parquet(ledger_path)
    leaked = {"is_anomalous", "anomaly", "anomalies", "decoys", "truth", "label"}
    assert not leaked & set(reloaded.columns), "ground truth leaked into the ledger file"
