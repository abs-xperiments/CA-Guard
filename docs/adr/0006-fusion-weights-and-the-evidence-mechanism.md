# ADR-0006 — Fusion weights, and whether the evidence gap earns its place

- **Date:** 2026-09-06
- **Status:** Accepted
- **Phase:** 4
- **Required by:** ADR-0003 rule 4 (weights committed before the held-out run)

## Context

Phase 3 left a hard bar. The rules alone already reach **100% recall with zero legitimate entries queued**, so fusion cannot win on recall — there is nothing left to find. What it can improve is **ordering**: how much of a reviewer's finite attention lands on something real.

Phase 4 also had to answer a question the project has been asserting since Phase 0. `docs/03_PATENT_AND_IP.md` singles out **evidence-gap-driven prioritisation** as the one candidate mechanism the prior-art search did not find occupied. Until now that was a claim. This phase makes it an experiment.

## The fusion

Noisy-OR, not a weighted sum: `priority = 1 − Π(1 − wₖ·sₖ)`, with an evidence uplift applied to the remaining headroom.

A sum lets three weak concerns outrank one decisive concern and runs past 1 without meaning anything. Noisy-OR treats each signal as independent evidence, stays in [0, 1], and reads plainly as "the chance at least one of these concerns is real".

## Frozen weights

| Signal | Weight | Reasoning |
|---|---|---|
| `missing_evidence` | 0.90 | The evidence gap is the concern this project is built around. |
| `duplicate_entry` | 0.85 | Direct cause of leakage; measured at 100% recall. |
| `period_end_concentration` | 0.80 | An undocumented year-end adjustment is an SA 240 characteristic. |
| `post_close_entry` | 0.75 | Entered after the books closed. |
| `rare_account_pair` | 0.70 | Strong when it fires, and it abstains when it cannot discriminate. |
| `off_hours_posting` | 0.65 | Only meaningful where posting times are real. |
| `round_amount` | 0.60 | Real but common; the decoys show why it needs corroboration. |
| `unusual_preparer_account` | 0.60 | Population-dependent; 90% recall on held-out seeds. |
| `weekend_posting` | 0.50 | Narrow by design — Sunday only. |
| `amount_outlier` | 0.40 | High precision but only 10% recall. |
| `threshold_adjacent` | 0.35 | **Measured precision ≈ 5%.** Sitting under a limit is the ordinary case. |
| `ml_anomaly` | 0.15 | Found nothing the rules missed and queued legitimate entries (ADR-0005). |
| evidence gap (uplift) | 0.45 | Applied to the headroom left by the signals. |

`ml_anomaly` **may not raise a voucher on its own** (D-020), enforced in `fusion._corroborated`, not in prose.

## Result — held-out seeds 101–105, 4,000 vouchers, 80 planted each

| Variant | Queue | p@10 | p@25 | p@50 | Items to reach 95% | Recall |
|---|---|---|---|---|---|---|
| **fusion (full)** | 233 | **1.00** | **1.00** | **0.88** | **157** | 0.998 |
| no evidence uplift | 233 | 1.00 | 1.00 | 0.87 | 157 | 0.998 |
| **no evidence at all** | 230 | **0.70** | **0.82** | 0.82 | **215** | **0.960** |
| no model | 233 | 1.00 | 1.00 | 0.88 | 157 | 0.998 |
| **unranked (ledger order)** | 233 | **0.44** | **0.34** | **0.32** | **229** | 0.998 |

### 1. Ranking is the win, and it is a large one
Against the same queue in ledger order, fusion takes precision in the first 25 items from **34% to 100%**, and in the first 50 from 32% to 88%. A reviewer working the top of the list sees something real every time instead of one in three. Reaching 95% of the findings takes 157 items instead of 229 — **31% less work**.

### 2. Evidence information is load-bearing
Removing evidence entirely — both the uplift and the `missing_evidence` rule — costs **30 points at p@10**, 18 at p@25, pushes the work needed to reach 95% from 157 to 215 items, and drops recall from 99.8% to 96%.

That is the clearest support so far for the mechanism `docs/03_PATENT_AND_IP.md` identifies. It remains a **candidate**, not a novelty claim, and the prior-art position is unchanged.

### 3. But the separate uplift term is nearly redundant
With the rule in place, the uplift adds **1.6 points at p@50 and nothing anywhere else**. The work is done by evidence as a *detection signal*, not by evidence as a score adjustment.

This is worth stating plainly because it sharpens what the mechanism actually is: evidence availability matters to prioritisation, and the effective way to use it is to let it raise a finding, not to nudge a score afterwards. The uplift is retained — it costs nothing and covers partial gaps the rule does not reach — but it is not what makes the difference.

### 4. The model still contributes nothing
"no model" is identical to the full variant on every measure. Consistent with ADR-0005, and the low weight plus the corroboration rule are doing their job of keeping it harmless.

## Honest limits

Same as ADR-0005: the anomalies are rule-shaped because we wrote both the rules and the planting, and the ledger is synthetic. What is shown is that **ordering by fused priority, with evidence in the mix, substantially reduces the work of finding what is there.** Whether the ordering holds on a real client ledger is untested and needs real data.

## Consequences
- Changing any weight requires a fresh held-out run and a journal entry.
- Phase 6's UI should lead with the high band and show the contributions, since the ranking is the product.
- The near-redundancy of the uplift should be revisited if the evidence model becomes richer (attachments, three-way match), where a rule may be too blunt.
