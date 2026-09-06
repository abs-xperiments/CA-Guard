# ADR-0007 — Local model strategy: architecture first, Qwen3 1.7B, and a hard memory gate

- **Date:** 2026-09-06
- **Status:** Accepted; model installed and evaluated 2026-09-06
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

## Installation: unblocked, installed, measured

The founder approved freeing memory (quitting Docker Desktop and three
background applications). **Docker Desktop was reserving 4.1 GB of the 8 GB
machine** for two containers belonging to another project — more than half the
memory, for something unrelated to CA-Guard.

| | Before | After |
|---|---|---|
| Swap in use | 7.51 GB | **3.02 GB** |
| Compressed | 2.89 GB | 2.21 GB |

Ollama 0.33.3 and `qwen3:1.7b` (**Q4_K_M confirmed**, 1.4 GB) installed. Free, no
account, no key. Total spend: ₹0.

## The model needed fixing, and it was the prompt — not the size

First real inference returned **nothing** after 29.6 seconds. Diagnosed rather
than assumed, per founder instruction 9:

| Setting | Time | Reasoning | Answer |
|---|---|---|---|
| default (reasoning on) | 24.7s | 1,409 chars | truncated, sometimes empty |
| **`think: False`** | **7.4s** | none | complete |

Qwen3 reasons before answering unless told not to. It was spending its whole
token budget thinking and hitting the cap mid-sentence. There is nothing to
reason about here — the finding is already decided — so reasoning is disabled.
**Four times faster, and it works.**

## Controlled evaluation — 20 findings, seed 101

| | Model text used | Factual consistency | Evidence coverage | Unsupported claims | Words | Readability | Latency |
|---|---|---|---|---|---|---|---|
| **deterministic (no model)** | — | **1.00** | **1.00** | **0** | 101 | easy (10 w/s) | **0.0s** |
| **qwen3:1.7b Q4_K_M** | **20/20** | **1.00** | 0.93 | **0** | **76** | easy (16 w/s) | 6.3s median |

**Every one of the twenty explanations passed the guard.** No invented numbers,
no conclusive language, on any finding.

### The prompt closed the one gap

Coverage started at 0.858 — the model was quietly omitting concerns, exactly the
weakness the stub had predicted. Instruction 9 says fix the prompt before
reaching for a bigger model. Tightening it to demand every concern be mentioned:

| | Before | After |
|---|---|---|
| Evidence coverage | 0.858 | **0.925** |
| Words | 94 | **76** |
| Latency | 6.96s | **6.29s** |

Shorter, faster **and** more complete. **No larger model was needed or proposed.**

## How the two compare

Neither is simply better.

- **Deterministic** is complete (100% coverage), instant, and never wrong. It
  reads slightly mechanically — one clause per concern, 101 words.
- **Qwen3 1.7B** reads more naturally in a quarter fewer words, at 93% coverage
  and about 6 seconds a finding. The 7% it drops is the cost of prose.

For a reviewer working through fifty findings, six seconds each is six minutes
of waiting. The default therefore stays **no model**, with generated prose as an
option a firm turns on.

## Resource use, measured

| | |
|---|---|
| Model on disk | 1.4 GB |
| Latency | 4.8s min · 6.3s median · 9.9s max |
| Swap during a 20-finding run | 4.64 → 5.05 GB |

Swap still climbs during inference. This machine can run the model, but not
comfortably alongside much else — which is a fact about the laptop, not the
design.

## Limitations

1. **Measured on one machine under memory pressure.** Latency would improve
   materially with more RAM.
2. **20 findings from one seed.** Enough to show the guard holds and the prompt
   fix worked; not a broad quality study.
3. **Coverage is measured by keyword matching**, which is approximate. It cannot
   tell a mention from a good explanation.
4. **English only.** No Hindi or regional-language output was tested.
5. **The guard cannot catch a plausible-but-wrong *characterisation*** — only
   invented numbers and conclusive language. A model that describes a real
   figure misleadingly would pass. This is the main residual risk and the reason
   the deterministic path remains the default.

## Consequences

- The application is complete and shippable with **no model at all**, and that
  remains the default: `caguard explain` needs nothing installed.
- A local model is opt-in prose polish: `--model qwen3:1.7b`.
- Any future provider must satisfy the same guard and the same loopback rule.
- Reasoning mode must stay off for any thinking-capable model.
- **Nothing was spent.** Ollama and Qwen3 are free; no account, key or card.
