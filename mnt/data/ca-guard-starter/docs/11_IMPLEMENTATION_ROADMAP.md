# Three-Month Implementation Roadmap

## Phase 0 — Research, validation, freeze
Acceptance:
- market/prior-art map updated;
- dataset/license verified;
- architecture/stack frozen;
- research hypothesis and metrics defined;
- no implementation started before sign-off.

## Phase 1 — Repository and data foundation
Build:
- app skeleton;
- canonical transaction schema;
- upload/parser layer;
- dataset generator;
- validation pipeline.

Acceptance: supported demo dataset ingests reliably with automated tests.

## Phase 2 — Deterministic audit-review signals
Build:
- duplicate-like detection;
- round-number patterns;
- off-hours/weekend patterns;
- period-end concentration;
- rare account-pair signals;
- threshold-adjacent patterns;
- missing evidence-reference signal.

Acceptance: planted anomalies are detected with known ground truth.

## Phase 3 — Statistical + ML anomaly engine
Build:
- baseline statistics;
- one primary ML model such as Isolation Forest;
- standardized feature pipeline;
- model versioning/config.

Acceptance: deterministic evaluation and baseline comparison pass.

## Phase 4 — Risk fusion + evidence
Build:
- transparent weighted risk fusion;
- evidence completeness score;
- finding object schema;
- source-row linkage.

Acceptance: every finding can show its contributing signals and evidence.

## Phase 5 — Local/private AI explanation
Build:
- structured explanation prompt;
- local model adapter;
- deterministic fallback text when LLM unavailable;
- guardrails preventing unsupported claims.

Acceptance: explanation tests pass; no cloud call in private mode.

## Phase 6 — Product UI/UX
Build:
- polished dashboard;
- finding table;
- evidence drawer;
- review decisions;
- progress/error states;
- micro-animations.

Acceptance: full happy path works from upload to decision.

## Phase 7 — Evaluation, hardening, deployment
Build:
- benchmark runner;
- report export;
- security checks;
- Docker self-hosted mode;
- Railway demo;
- final documentation.

Acceptance: end-to-end demo, clean repo, documented metrics, reproducible deployment.

## Time discipline
If a feature does not support the core research hypothesis, user workflow, evaluation, or demo, defer it.
