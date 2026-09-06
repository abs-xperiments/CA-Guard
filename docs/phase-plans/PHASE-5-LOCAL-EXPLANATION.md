# Phase 5 — Local, private explanation

**Founder direction, 2026-09-06:** architecture and tests first; deterministic fallback is a first-class path, not a fallback of last resort; the Ollama adapter is built and tested against a stub before anything is downloaded; **Qwen3 1.7B Q4_K_M** is the first real model, not 4B; nothing is installed until the tests are green and the machine has the memory.

## The one rule everything else follows from

> The model **explains a Finding that has already been computed**. It is not the accounting engine, not the detector, and it may never reach an audit conclusion of its own.

Detection, scoring and ranking are complete before a single token is generated. If the model is absent, broken, slow or wrong, the review queue is unchanged and the product still works. That is not a degraded mode — it is the normal mode with prose attached.

## Design decisions

### D1 — The deterministic explanation is a real deliverable, not a stub
It is what a firm running CA-Guard with no model installed sees, and what every reviewer sees when the model's output is rejected. It has to read well enough that nobody feels short-changed. It is written first and tested hardest.

### D2 — The model sees only `Finding.structured_facts()`
No ledger rows, no free text, no context beyond the verified facts already computed. If a fact is not in that dict, the model has no basis to state it — a property of the data rather than an instruction in a prompt.

### D3 — Every generated sentence is checked before it is shown
An unsupported-claim guard runs on the output. Numbers that do not appear in the facts, account codes that were never mentioned, and conclusive language ("fraudulent", "must be", "proves") are all violations. **A failed guard means the deterministic text is shown instead** — the model does not get a second chance to be believed.

### D4 — The provider is abstract, and "no provider" is a supported configuration
`ExplanationProvider` is a protocol. Ollama is one implementation, the null provider another. Swapping or removing a provider changes no calling code.

### D5 — Local means local, and it is enforced
The Ollama adapter refuses any host that is not loopback. The strongest privacy claim this project makes is that client data never leaves the machine; a configuration mistake must fail closed rather than quietly post a ledger somewhere.

### D6 — If the small model reads badly, fix the prompt before reaching for a bigger one
Model size is the last thing to change, and only through a Founder Decision Gate.

## Deliverables

| # | Deliverable | Module |
|---|---|---|
| 1 | Verified facts, hardened | `review/finding.py` (`structured_facts`) |
| 2 | Deterministic explanation | `explain/deterministic.py` |
| 3 | Strict prompt construction | `explain/prompt.py` |
| 4 | Unsupported-claim guard | `explain/guard.py` |
| 5 | Provider protocol, null provider, stub | `explain/provider.py` |
| 6 | Ollama adapter, loopback-only | `explain/ollama.py` |
| 7 | Orchestration with fallback | `explain/service.py` |
| 8 | Comparison harness | `evaluation/explanations.py` |
| 9 | `caguard explain` command | `cli.py` |

## Test plan

| Test | Asserts |
|---|---|
| `test_deterministic` | reads as sentences; names every signal; states the evidence gap; never concludes |
| `test_facts_are_complete` | every signal, contribution and source line reaches the facts |
| `test_prompt_contains_only_facts` | no ledger row, no narration, nothing outside the dict |
| `test_guard_catches_invented_numbers` | a figure not in the facts is a violation |
| `test_guard_catches_conclusions` | "fraudulent", "must be", "proves" are violations |
| `test_guard_passes_grounded_text` | a faithful rendering is accepted |
| `test_service_falls_back_on_failure` | provider absent, slow, erroring, or guard-failing → deterministic text |
| `test_service_never_changes_the_finding` | priority, band and signals are identical before and after |
| `test_ollama_refuses_non_loopback` | a remote host is rejected outright |
| `test_no_network_without_a_provider` | the null path opens no socket |

## Acceptance criteria — **architecture met; model install blocked on memory**

- [x] Deterministic explanation implemented and good enough to ship alone
- [x] Model receives only `structured_facts()`
- [x] Guard rejects invented numbers and conclusive language
- [x] Provider abstract; disabled is a supported configuration
- [x] Ollama adapter tested against a stub, loopback enforced
- [x] **Application fully functional with no model installed**
- [x] ruff / pyright / pytest green
- [x] *Then* check free memory — **checked, and insufficient. Nothing downloaded.**
- [x] Controlled comparison: factual consistency, evidence coverage, unsupported claims, readability, latency
- [x] Model decision, results, resource use and limits recorded in `journal.md`

## Out of scope
UI (Phase 6). Any paid API, hosted inference, cloud GPU or containerised model as a substitute for the local one.

---

## Outcome (2026-09-06)

Architecture complete, **388 tests passing**, ruff and pyright clean. Full record in ADR-0007.

### The product works today with no model at all
`caguard explain` needs nothing installed. That is the default configuration, not a degraded one.

### Guard behaviour, measured over 20 findings

| Variant | Model text used | Factual consistency | Evidence coverage | Unsupported claims | Words | Readability |
|---|---|---|---|---|---|---|
| **deterministic (no model)** | — | **1.00** | **1.00** | **0** | 101 | easy (10 w/s) |
| stub: faithful model | 1.00 | 1.00 | **0.62** | 0 | 56 | easy (9 w/s) |
| stub: hallucinating model | **0.00** | — | — | — | — | — |

- **A hallucinating model never reached a reviewer.** Every output rejected and replaced.
- **The deterministic path beats a well-behaved model on evidence coverage** — 100% against 62%. Fluent prose summarises, and summarising drops concerns. A real trade-off to watch when a real model is measured.

### One correction the tests caught
The guard rejected **our own** text for showing a priority of `0.986722` as `0.99`. Rounding for a reader is faithful rendering, not invention. Found by a test asserting the always-on path satisfies its own guard — if our template cannot pass, the guard is wrong.

### 🔴 Model install blocked

| | |
|---|---|
| Total memory | 8.0 GB |
| Effectively available | **~1.4–2.0 GB** |
| **Swap in use** | **6.9–7.8 GB of 8.0 GB** |
| Qwen3 1.7B Q4_K_M needs | ~2.0–2.5 GB |

Per founder instruction 12, **nothing was downloaded**. Installing onto a swapping machine would make the latency measurement meaningless — timing page faults, not inference.

`make model-check` reports the position; `make model-install` runs the gate and refuses if the machine still cannot take it.
