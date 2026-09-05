# Patent and Intellectual Property Strategy

## Status
**Patent candidate — not a guaranteed patent.**

A project title does not create patent rights. Patentability depends on the specific claims and prior art.

> **Correction, 2026-09-06 (Phase 0).** The IP India guidance published **7 August 2026** governs *examiners' and controllers' use of AI while examining patents* (search, classification, translation, drafting support). It **does not change what is patentable**. Patent eligibility for CA-Guard remains governed by the **CRI Guidelines 2025 (issued 29 July 2025)**, which retain the §3(k) exclusions and make demonstrable **"technical effect"** the gateway. Any earlier wording implying the 2026 document is AI-patentability guidance was wrong.

## India-specific issue
IP India has current 2025 Computer Related Inventions (CRI) Guidelines. The project must not rely on a generic “algorithm on a computer” claim. The claim strategy should investigate whether the specific technical architecture produces a defensible technical contribution/effect and remains eligible under current Indian practice.

Primary source:
https://ipindia.gov.in/resource/patents-resources-guidelines

2025 CRI PDF:
https://ipindia.gov.in/frontend/pdf/patents/guidelines/GUIDELINES%20FOR%20EXAMINATION%20OF%20COMPUTER%20RELATED%20INVENTIONS%20%28CRIs%29%20-%202025.pdf

## Known crowded areas
Prior art already exists for:
- autonomous accounting anomaly detection (HighRadius, US12293420B2);
- AI-augmented audit evidence/vouching (US20230005075A1);
- financial risk scoring and transaction anomaly analytics;
- AI-assisted reconciliation;
- evidence/traceability in audit systems.

Sources:
- https://patents.google.com/patent/US12293420B2/en
- https://patents.google.com/patent/US20230005075A1/en

## Prior art read in full claim text (Phase 0, 2026-09-06)

| Reference | Status | Relevance |
|---|---|---|
| **US12293420B2** — HighRadius, *Autonomous accounting anomaly detection engine* | **Granted** 2025-05-06, active to 2043 | Claim 1: receive GL entries → ML correlation against historical baselines → threshold deviations → **prioritized** recommendations → real-time display. Closest granted art to our core loop. Differs: real-time-at-entry, correction recommendations, no deterministic audit-rule layer, no evidence-completeness input, no LLM explanation. |
| **US20230005075A1** — PwC, *AI-augmented auditing platform … vouching evidence* | **Pending**, filed 2022-06-30 | Extracts document data and scores whether it constitutes valid vouching evidence, with confidence scores linked to ERP line items. Occupies "evidence sufficiency scoring" directly. |
| **US11694460B1** — Wells Fargo, *NLP … audit testing with documentation prioritization* | Granted 2023-07-04 | Ranks documents by **semantic similarity** to audit terms, **not** by presence/absence of supporting evidence. Distant from our mechanism. |
| **CORAA** — "patent-pending deterministic LLM architecture" | Unknown, likely unpublished | 🔴 **Highest India-specific risk.** Indian applications publish at 18 months; a recent filing is invisible to any search today. Structurally unsearchable. |

### Clearly already known — do not claim
ML financial anomaly detection; transaction risk scoring; **rules + statistics + ML ensembles** (MindBridge, shipped); AI-assisted vouching and evidence matching (PwC); citation-grounded audit explanation (Caseware, shipped); AI reconciliation.

### The single surviving candidate mechanism
Five of the six candidates listed below are covered by the art above. The one that this search did not find occupied:

> **Using the *absence or incompleteness of linked supporting evidence* as a first-class weighted input into anomaly-review priority ranking** — so that an otherwise-ordinary transaction is promoted specifically because its evidence trail is missing, with the ranking degrading gracefully and deterministically when the explanation model is unavailable.

Why it may be arguable: PwC scores evidence *that exists*; Wells Fargo ranks by *semantic content*; HighRadius ranks by *statistical deviation*. Ranking driven by an **evidence gap** is a different input. Under CRI 2025 the technical-effect argument would rest on the deterministic, offline-capable ranking pipeline — not on "AI finds fraud".

**This is a lead for a patent attorney, not a conclusion. It must not be represented to any third party as novel.** This search was non-exhaustive: US full text was read; Indian InPASS was not systematically mined.

## Potential technical focus for further review
Rather than patenting “AI detects accounting fraud”, investigate a narrower mechanism around:
1. local/private ingestion and processing controls;
2. canonical financial-data normalization across heterogeneous inputs;
3. fusion of independently generated anomaly signals;
4. evidence availability/completeness influencing review prioritization;
5. generation of an evidence-linked explanation from structured machine findings;
6. auditable human decision state and review trail.

The exact claim boundary must be discovered by a patent professional after a formal search.

## Publication timing warning
Before public disclosure of the detailed invention, consult a patent professional about filing strategy. Academic publication and patent filing should be coordinated.
