# Phase 6 — The review workspace

**Goal:** a CA can open a ledger, work down a prioritised queue, inspect the evidence behind any finding, record a professional decision, and export the result — end to end.

## What this phase is really about

Everything before now produced a good answer. This is where it becomes usable. Phase 4 measured why that matters: the *same* findings in ledger order gave a reviewer 34% precision in their first 25 items; ranked, it was 100%. The ordering is the product, and the interface is how anyone actually benefits from it.

The bar from `docs/09_UI_UX.md`: a calm professional audit workspace, not a flashy AI toy. Dense but readable tables. Evidence first, AI prose second.

## Built in three parts

**6a — Review state** (`review/store.py`, `review/decisions.py`)
The decisions a reviewer records, and the audit trail behind them. Pure Python, SQLite, no server needed.

**6b — API** (`api/`)
FastAPI over the existing pipeline. Local-only by default.

**6c — Workspace** (`web/`)
Next.js 16 + Tailwind v4 + shadcn-style components, owned in-repo.

## Design decisions

### D1 — Decisions are append-only
A review trail that can be edited is not a review trail. Every decision is a new row; the current position is the latest one. A reviewer changing their mind is itself a fact worth keeping, and an engagement quality reviewer will ask.

### D2 — Rejecting requires a reason
Accepting a finding says "yes, I looked". Rejecting says "this is not a concern", and that is the judgement someone may question later. It must carry a note.

### D3 — Findings are derived, decisions are stored
We never persist a computed finding. Re-running the same ledger at the same version reproduces it exactly (that is what the content hash is for), and storing it would let the stored copy drift from what the code now says. Decisions reference the voucher.

### D4 — SQLite, single file, no server
The privacy story is local processing. A local file needs no daemon, no port and no credentials, and a firm can back it up by copying it.

### D5 — The API binds to loopback by default
Same reasoning as the model adapter: a mistyped bind address must not quietly expose a client ledger on the office network.

### D6 — The UI must work with no model installed
Explanations come from the deterministic path unless a firm turns a model on. The interface must never look broken because there is no AI.

## Deliverables

| # | Deliverable | Module |
|---|---|---|
| 1 | Review actions and decision records | `review/decisions.py` |
| 2 | SQLite store, append-only, migrated | `review/store.py` |
| 3 | Engagement lifecycle (open a ledger, keep its identity) | `review/engagement.py` |
| 4 | Report export (CSV + HTML) | `review/report.py` |
| 5 | FastAPI application, loopback-bound | `api/app.py` |
| 6 | Next.js workspace | `web/` |
| 7 | `caguard serve` and `caguard export` | `cli.py` |

## Test plan

| Test | Asserts |
|---|---|
| `test_store_is_append_only` | a second decision adds a row, never replaces one |
| `test_reject_requires_a_reason` | rejection without a note is refused |
| `test_current_state_is_the_latest_decision` | history preserved, position correct |
| `test_engagement_records_the_ledger_identity` | content hash stored, so drift is detectable |
| `test_schema_migrates_from_empty` | a fresh file works; re-opening does not re-migrate |
| `test_report_contains_every_reviewed_finding` | nothing silently dropped from an export |
| `test_api_binds_to_loopback` | a non-local bind is refused |
| `test_api_happy_path` | upload → analyse → findings → decision → export |
| `test_api_works_without_a_model` | explanations are still returned, from the deterministic path |

## Acceptance criteria

- [ ] Decisions recorded with an append-only audit trail
- [ ] Rejection requires a reason
- [ ] Engagement stores the ledger's content hash
- [ ] Report export covers every reviewed finding
- [ ] API loopback-bound; full happy path works
- [ ] Workspace: queue, filters, evidence drawer, decision actions, empty/loading/error states, keyboard navigation
- [ ] Everything works with no model installed
- [ ] ruff / pyright / pytest green; docs, journal, clean commit

## Out of scope
Deployment, Docker, Railway (Phase 7). Multi-user accounts and permissions — a single reviewer on one machine is the product being built.
