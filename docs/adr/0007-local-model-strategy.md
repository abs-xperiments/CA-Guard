# ADR-0007 — Local model strategy: architecture first, Qwen3 1.7B, and a hard memory gate

- **Date:** 2026-09-06
- **Status:** Accepted; model installation **blocked on available memory**
- **Phase:** 5
- **Founder direction:** build the architecture and tests before downloading anything; deterministic fallback is first-class; Qwen3 **1.7B** Q4_K_M, not 4B; no hosted inference, no cloud GPU, no containerised model as a substitute; ₹0 throughout.

## The rule the design serves

> The model **renders** a Finding that has already been computed. It is not the accounting engine, does not detect, does not rank, and may never reach an audit conclusion of its own.

Everything below follows from that. Detection, scoring and ranking finish before a token is generated, so the review queue is byte-identical whether a model is installed, missing, broken or wrong.

## What was built, in the order the founder specified

1. **Deterministic explanation** (`explain/deterministic.py`) — a real deliverable. It is what a firm with no model installed reads, and what every reviewer reads when generated text is rejected. Written first, tested hardest.
2. **Verified facts only** — the model sees exactly `Finding.structured_facts()`: no ledger rows, no narrations, no customer names. Anything it says beyond those facts is by construction invented.
3. **Strict prompt** (`explain/prompt.py`) — instructs rewriting, not assessment, and pre-formats the rupee amount so the model is never asked to divide by 100. An arithmetic slip reads exactly like an invented figure.
4. **Unsupported-claim guard** (`explain/guard.py`) — every number must trace to the facts; conclusive language ("fraudulent", "proves", "must be") is a violation. **A failure discards the text.** No second attempt.
5. **Abstract provider** (`explain/provider.py`) — a protocol. Ollama is one implementation, `NullProvider` another. "No model" is a supported configuration, not an error.
6. **Ollama adapter** (`explain/ollama.py`) — **loopback enforced at construction**. A non-loopback host raises rather than warns: the strongest claim this project makes is that client data never leaves the machine, so a mistyped host must fail closed.
7. **Tested against a stub** — the whole path (prompt → generation → guard → fallback) is exercised with no download.

## Guard behaviour, measured

20 findings, three variants:

| Variant | Model text used | Factual consistency | Evidence coverage | Unsupported claims | Words | Readability |
|---|---|---|---|---|---|---|
| **deterministic (no model)** | — | **1.00** | **1.00** | **0** | 101 | easy (10 w/s) |
| stub: faithful model | **1.00** | 1.00 | **0.62** | 0 | 56 | easy (9 w/s) |
| stub: hallucinating model | **0.00** | 1.00 | 1.00 | 0 | 101 | easy |

Two things worth stating:

- **The hallucinating stub never reached a reviewer.** Every output was rejected and replaced. Its scores are the deterministic scores, because that is what was shown.
- **The deterministic path currently beats a well-behaved model on evidence coverage** — 100% against 62%. Fluent prose summarises, and summarising means quietly dropping concerns. That is a real trade-off, not a bug in the stub, and it is the thing to watch when a real model is measured.

## One rounding correction

The guard initially rejected **our own** deterministic text, because it displayed a priority of `0.986722` as `0.99`. Rounding a fact for a reader is faithful rendering, not invention, so the guard now accepts any sensible precision of a value that is present. Caught by a test asserting that the always-on path satisfies its own guard — if our template cannot pass, the guard is wrong.

## Model choice

**Qwen3 1.7B, Q4_K_M** (`qwen3:1.7b`), per founder direction. Roughly 1.4 GB resident. The earlier suggestion of a 4B model is withdrawn.

Determinism is pinned: `temperature=0.0`, fixed seed, `num_predict=400`. A `<think>` block, which Qwen3 may emit, is stripped before the guard sees the text — reasoning is working material, not an explanation.

## 🔴 Installation is blocked, and why

Measured on this machine immediately after the tests went green:

| | |
|---|---|
| Total memory | 8.0 GB |
| Effectively available | **1.42 GB** |
| Compressed | 2.68 GB |
| **Swap in use** | **6.87 GB of 8.0 GB** |
| Qwen3 1.7B Q4_K_M needs | ~1.4 GB resident + ~0.5 GB context ≈ **2.0 GB** |

The machine is already swapping heavily. Installing now would not merely be slow — it would make the **latency measurement meaningless**, because we would be timing page faults rather than inference, and it risks making the machine unusable while it runs.

Founder instruction 12 says not to download until the machine has sufficient free RAM. It does not. **No download was made.**

## What happens when memory is available

`make model-install` (three free commands, no account, no key), then the comparison harness re-runs unchanged and the results replace the stub rows above.

If Qwen3 1.7B reads poorly, instruction 9 applies: **investigate the prompt and the facts first.** The 62% coverage figure from the faithful stub already points at where the problem is likely to be — prose that summarises drops concerns — and that is a prompt problem, not a parameter-count problem. A larger model is proposed only through a Founder Decision Gate.

## Consequences

- The application is complete and shippable **today** with no model at all.
- `caguard explain --model none` is the default and needs nothing installed.
- Any future provider must satisfy the same guard and the same loopback rule.
- Nothing was spent. Nothing was downloaded.
