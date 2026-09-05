"""Benchmark generation — the project-owned Indian ledger and its ground truth.

**Nothing outside this package may import from it.** ADR-0003 rule 1 makes the
generator and the detectors separate powers: if a detector could read the
generator's constants or its planted truth, every metric we publish would be
circular. ``tests/test_isolation.py`` enforces this by walking the AST of every
other module, so the rule fails CI rather than relying on memory.
"""
