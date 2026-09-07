# Phase 7 — Evaluation, hardening, deployment

**Goal:** make the research result reproducible by someone else, make the application safe to run on a firm's machine, and give it a deployment path that costs nothing.

**Founder constraint (C-1, reaffirmed):** no purchases. Local Docker and a zero-cost reproducible demo. Railway is revisited only after the product is finished, and only as a decision the founder makes.

## What this phase has to prove

Six phases produced measurements scattered across ADRs and journal entries. A reader who wants to check them currently has to trust prose. That is not good enough for something being written up as research, so the headline claims become **one command that regenerates them**:

| Claim | Where it came from |
|---|---|
| Ten signals find their planted anomalies; none falls for its decoy | Phase 2, ADR-0004 |
| The model finds nothing the rules missed, and queues legitimate entries | Phase 3, ADR-0005 |
| Ranking takes precision@25 from 34% to 100% | Phase 4, ADR-0006 |
| Evidence information is load-bearing in the ranking | Phase 4, ADR-0006 |

If a number in the write-up disagrees with what the runner prints, the write-up is wrong.

## Design decisions

### D1 — The benchmark runner reports, it does not tune
It runs held-out seeds against frozen thresholds and prints what it finds. There is no flag that improves the result, because a benchmark you can adjust is a benchmark that will be adjusted.

### D2 — Security checks are part of the gate, not a one-off review
Dependency vulnerabilities, a secrets scan and ruff's security rules run in `make check` and in CI. A check performed once is a check that is out of date.

### D3 — The Docker image runs the whole thing offline
Ledger analysis must work with no network at all — that is the privacy claim, and an image that quietly needs the internet would break it without anyone noticing.

### D4 — Public deployment is a founder decision, not a default
Railway is cloud infrastructure. Deploying there means a public URL, a monthly cost, and a claim that must be worded carefully (D-005: the demo is not the private product). It stays unbuilt until the founder says otherwise.

## Deliverables

| # | Deliverable | Where |
|---|---|---|
| 1 | Benchmark runner producing every headline number | `evaluation/benchmark.py`, `caguard benchmark` |
| 2 | Results, regenerated and committed | `docs/RESULTS.md` |
| 3 | Dependency audit, secrets scan, security lint | `make audit`, CI |
| 4 | Self-hosted Docker image and compose file | `Dockerfile`, `compose.yaml` |
| 5 | Deployment and operation guide | `docs/deploy.md` |
| 6 | Final documentation pass | `README.md`, `docs/` |

## Test plan

| Test | Asserts |
|---|---|
| `test_benchmark_is_reproducible` | two runs on the same seeds produce identical numbers |
| `test_benchmark_uses_held_out_seeds` | it refuses to report on a seed used for tuning |
| `test_no_secrets_in_the_repository` | no key, token or credential is committed |
| `test_analysis_needs_no_network` | the pipeline runs with sockets disabled |
| `test_docker_files_are_coherent` | the image and compose file reference what exists |

## Acceptance criteria — **all met, 2026-09-07**

- [x] `caguard benchmark` regenerates every headline number
- [x] `docs/RESULTS.md` written from that output, not from memory
- [x] Dependency audit and secrets scan clean, wired into `make check` and CI
- [x] Analysis proven to work with no network
- [x] Docker image builds and runs the full stack offline
- [x] Deployment guide covers the private path end to end
- [x] ruff / pyright / pytest green; docs, journal, clean commit
- [x] Railway raised as a founder decision, **not** built

## Out of scope
Any public deployment, paid hosting, or spend of any kind.

---

## Outcome (2026-09-07)

### Every claim is now one command

`caguard benchmark --out docs/RESULTS.md` regenerates the lot on held-out seeds against frozen thresholds. `docs/RESULTS.md` is written from that output and carries a fingerprint. It refuses to run on a seed used during development.

| Claim | Regenerated |
|---|---|
| Ten signals find their anomalies; **0** fall for their decoys | ✅ |
| The model finds **nothing** the rules missed, on every seed | ✅ |
| Ranking: precision@25 **34% → 100%** | ✅ |
| Effort to find 95%: **229 → 157** vouchers | ✅ |
| Evidence removed: p@10 **100% → 70%**, recall 99.8% → 96% | ✅ |

### Security is part of the gate, not a review

`make check` now runs the dependency audit alongside lint, types and tests, and CI does the same. **Both audits clean** — 0 Python vulnerabilities, 0 Node.

17 security tests, including the one that matters most: **the whole pipeline runs with every socket call raising**. That is the privacy claim proven rather than asserted.

**One real weakness found and fixed.** `Path("..\\..\\windows\\x").suffix` returns `".\\windows\\x"` on POSIX, because a backslash is not a separator there — and the API was putting that straight into a temporary filename. Harmless on macOS, a traversal on Windows. Upload suffixes are now matched against an allowlist rather than trusted.

### The self-hosted image works

Built, run, and tested end to end:

| | |
|---|---|
| Container health | healthy |
| Runs as | `uid 10001`, never root |
| Workspace | reachable on loopback |
| **Analysis API** | **not published** — loopback inside the container only |
| Upload through the container | 24 findings from 431 vouchers |
| Decisions after a restart | preserved, note intact |
| Image size | 1.19 GB |

### Railway: raised, not built

Nothing deployed, nothing spent. The decision and its consequences are written up in `docs/deploy.md` for the founder.
