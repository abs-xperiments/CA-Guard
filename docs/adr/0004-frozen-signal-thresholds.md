# ADR-0004 — Frozen detector thresholds

- **Date:** 2026-09-06
- **Status:** Accepted
- **Required by:** ADR-0003 rule 4 (thresholds committed before the held-out run)

## Context
Ten deterministic signals each carry thresholds. Left loose in code they would drift toward whatever made the benchmark look good — the precise circularity ADR-0003 exists to prevent. They are therefore collected in a single `DetectorConfig`, recorded here, and committed before results are reported.

They are **defaults for a mid-size Indian firm, not truths.** A delegation limit and a materiality level are engagement decisions; the config is meant to be overridden per client.

## The thresholds

| Setting | Value | Reasoning |
|---|---|---|
| `approval_limit_paise` | ₹50,000 | Firm-specific delegation limit. Overridden per engagement. |
| `threshold_band_paise` | ₹5,000 | 10% of the limit. A band of a few hundred rupees would only catch someone hugging the line to the last rupee, which is not how a payment gets split. |
| `materiality_paise` | ₹25,000 | Below this an entry is not worth a reviewer's time. |
| `round_step_paise` / `round_min_paise` | ₹10,000 / ₹50,000 | Catches manufactured figures without firing on every invoice ending in a zero. |
| `routine_repeat_count` | 3 | An (account, amount) pair seen this often is a lease or an instalment. |
| `off_hours_start` / `off_hours_end` | 22:00 / 06:00 | Outside any plausible working day. |
| `duplicate_window_days` | 7 | Wide enough for a re-run, narrow enough that a monthly instalment never qualifies. |
| `period_end_window_days` | 3 | Entries dated at the year end. |
| `rare_pair_max_count` / `rare_pair_max_share` | 2 / 0.1% | Relative, because a fixed count does not scale between a 200-voucher ledger and a 40,000-voucher one. |
| `unfamiliar_preparer_max_share` | 5% | Share of an account's entries. |
| `unfamiliar_preparer_max_entries` | 3 | **And** an absolute ceiling. Share alone is not enough: an automated feed can hold 2% of a busy cash account across thirty entries, and thirty entries is not unfamiliarity. |
| `dominant_owner_min_share` | 50% | The account must have a clear regular owner. With six preparers the average share is already 17%, so a bare share test flags nearly everything. |
| `unfamiliar_preparer_min_account_entries` | 8 | A one-off account should not flag everyone who touches it. |
| `post_close_lag_days` | 45 | A posting lag beyond this suggests the entry followed the close. |

## Held-out result (seeds 101–105, never used while developing the thresholds)

4,000 vouchers per seed, 2% planted anomaly rate, 5% decoys. **Re-run after the
ledger was restructured** following the internal CA review
(`docs/ca_validation/findings.md`), which changed the population substantially.

| Signal | Mean recall | Min | Trap false positives |
|---|---|---|---|
| `duplicate_entry` | 100% | 100% | 0 |
| `round_amount` | 100% | 100% | 0 |
| `off_hours_posting` | 100% | 100% | 0 |
| `weekend_posting` | 100% | 100% | 0 |
| `period_end_concentration` | 100% | 100% | 0 |
| `rare_account_pair` | 100% | 100% | 0 |
| `threshold_adjacent` | 100% | 100% | 0 |
| `missing_evidence` | 100% | 100% | 0 |
| **`unusual_preparer_account`** | **90%** | **75%** | 0 |
| `post_close_entry` | 100% | 100% | 0 |

**Queue: 5.9% of vouchers**, containing 100% of planted anomalies on every seed,
with **0 of 1,000 decoys** wrongly queued.

`unusual_preparer_account` needs the account to have a clear regular owner, and
not every account in a realistic ledger does — Sundry Creditors, for instance, is
shared between purchasing and treasury. Its test floor is 0.60, below the
observed 75% minimum on purpose: a floor pinned to the observed number is a
floor tuned to this benchmark.

`threshold_adjacent` is the lowest-precision signal (about 5%). Sitting under a
delegation limit without an approver is the ordinary case for a small payment,
not a rare one. It is kept because structuring is a real concern, but it is a
weak signal on its own and is a candidate for low weighting in Phase 4 fusion.

### Two detector bugs the restructured ledger exposed

1. **`rare_account_pair` looked up pairings in either direction.** Dr Sundry
   Creditors / Cr Bank is how every vendor payment is written; the reverse is a
   supplier refund and is genuinely rare. Taking the rarer direction flagged
   ordinary payments as unusual pairings — 18% of the ledger. Pairings are now
   directional.
2. **`unusual_preparer_account` was unreachable on small accounts.** Five percent
   of a thirteen-entry account is 0.65, so even a single entry failed the test.
   A floor of one entry was added: one entry on an account owned by someone else
   is exactly the case the signal exists for.

## Abstention

Two signals return nothing rather than guess when the ledger cannot support them. This is a design rule, not a special case:

- **`off_hours_posting`** is silent when the source has no real posting time. Every VynFi posting is midnight; reading that as fact would flag all 667,584 lines.
- **`rare_account_pair`** abstains when most pairings in the ledger already fall under the rarity ceiling. Found on VynFi, where a chart of thousands of GL codes made the signal flag **95% of 53,291 vouchers**. With the guard it abstains there, and the overall VynFi queue falls from 95.6% to 13.3%, while benchmark recall is unchanged.

A signal that cannot discriminate on a given ledger should say so by staying quiet.

## Honest caveat
These thresholds were developed against seed 20250906 across several iterations. The table above is from seeds never used during that work, which is what makes it worth reading. It remains a result on synthetic data: no real Indian ledger has been evaluated, and the CA validation in `docs/ca_validation/` is the only external check on whether the data is plausible in the first place.

## Consequences
- Changing any value here requires a new held-out run and a journal entry saying why.
- Per-signal recall is reported, never a single blended figure (ADR-0003 rule 5).
