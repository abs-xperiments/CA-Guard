# Product Specification

## Primary user
A CA/accountant reviewing a client’s general ledger or transaction export.

## Core user journey
1. Create/open a review.
2. Upload or select a supported dataset.
3. Map/confirm columns.
4. Run analysis.
5. See a prioritized review queue.
6. Open a finding.
7. See risk score, signals, and evidence.
8. Ask “Why was this flagged?”
9. Review the explanation.
10. Record a professional decision.
11. Export a review report.

## Minimum product modules
### Intake
CSV/XLSX upload, schema validation, row-level error report.

### Analysis
Rules, statistical tests, ML anomaly model.

### Risk fusion
Transparent weighted score with signal-level breakdown.

### Evidence
Link findings to source rows and supporting document references when available.

### Explanation
Structured prompt to a local/private LLM. Explanation must only use supplied structured facts/evidence.

### Review
Accept / reject / modify / investigate.

### Reporting
Generate concise HTML/PDF/CSV review output depending on final stack constraints.

## Non-functional requirements
- local mode must work without cloud LLM access;
- clear failure states;
- audit trail for reviewer actions;
- no sensitive values in logs;
- deterministic analysis for the same input/version/seed;
- test coverage for core detection and scoring logic.
