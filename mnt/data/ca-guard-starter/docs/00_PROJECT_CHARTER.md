# CA-Guard — Project Charter

## One-line vision
CA-Guard is a private AI second-hand that helps CAs and accountants find, understand, and review unusual financial transactions faster.

## Formal title
**Design and Development of a Privacy-Preserving On-Premise Hybrid AI Framework for Evidence-Grounded Financial Anomaly Detection and Human-in-the-Loop Audit Review**

## The problem
A reviewer may have to inspect thousands of journal/transaction records to identify the small number that deserve attention. Manual screening is slow and can bury important exceptions in a large population.

## The proposed solution
CA-Guard accepts structured financial records, normalizes them, applies multiple independent signals, produces a prioritized review queue, retrieves relevant evidence, and generates a grounded explanation. The professional reviews the finding and remains the final decision-maker.

## What the first product does
- Upload CSV/Excel financial transaction data.
- Map common columns into a canonical journal-entry schema.
- Validate data quality.
- Run deterministic audit-review heuristics.
- Run statistical and ML anomaly detection.
- Fuse signals into a transparent priority score.
- Show evidence and the exact signals behind a finding.
- Provide an AI-generated explanation based on structured evidence.
- Let the reviewer accept, reject, modify, or mark for investigation.
- Export a review report.

## What it does not do
- Autonomous audit opinion.
- Tax/GST filing.
- Legal/accounting advice.
- Fraud accusation.
- Tally replacement.
- Full ERP functionality.
- General-purpose accounting chatbot.

## Success definition
A user can upload a supported dataset, get a useful prioritized review queue, inspect why items were flagged, review evidence, record a decision, and export a report, with the full workflow passing automated tests and demonstrable evaluation metrics.
