# CA-Guard — Final Completion Plan

**Audit date:** 2026-10-07 21:10 IST · **Baseline commit:** `695e904` · **Status:** audit complete; founder decisions answered; Phase 1 in progress

This plan comes from a full re-sync with the repository. That meant reading the code, docs, ADRs and journal, then actually *running* the product: the CLI, the API, the Next.js workspace in a browser, and the benchmark. Every defect below was reproduced, not inferred. Where something was not verified, it says so.

---

## 1. Current state in one paragraph

CA-Guard's core is real and good. A ledger goes through normalisation, ten deterministic signals, a statistical layer and an Isolation Forest, then an evidence-aware noisy-OR fusion, and comes out as a ranked review queue. Each finding carries its signals, contributions, evidence score and source line IDs. The explanation layer is honestly built: it uses facts only, has a number-and-phrase guard, falls back to deterministic text, and talks to the local model over loopback only. The review trail is append-only and signed by real accounts. The benchmark regenerates byte-identical results.

What stops it being a product a CA could use tomorrow is the layer *around* the core:
- it forgets uploaded ledgers on restart;
- it cannot accept a file over 10 MB through its own UI;
- it freezes for every user while one ledger is analysed;
- it shows the CA voucher IDs and account codes, not the transaction itself.

---

## 2. What was verified on 2026-10-07

| Check | Result |
|---|---|
| `ruff check`, `ruff format --check` | ✅ clean |
| `pyright` | ✅ 0 errors |
| `pytest -m "not slow"` | ✅ **534 passed** |
| `tsc --noEmit` (web) | ✅ clean |
| `caguard benchmark` vs committed `docs/RESULTS.md` | ✅ **reproduced identically** (40 s) |
| `pip-audit` (Python deps) | ✅ no known vulnerabilities |
| `npm audit --omit=dev` (web deps) | ❌ **3 vulnerabilities: 1 critical (Next.js 16.3.4, GHSA-vcvr-r3jv-pc5j), 2 high (sharp, source-map-js)**. The advisories are newer than the Phase 7 audit. CA-Guard does not import `next/og`, so the critical one is not directly reachable, but it must be patched. |
| Upload → queue, 3,034 vouchers (CSV and XLSX) | ✅ 1.1 s, 167 findings |
| Upload, 36,408 vouchers / 107k lines (26 MB) direct to API | ✅ 13.5 s |
| **Same 26 MB upload through the Next.js workspace** | ❌ **500 after 30 s.** Next.js truncates proxied bodies at 10 MB. |
| Health check *during* a 13.5 s analysis | ❌ **took 12 s.** Analysis blocks the event loop. |
| Restart the API, then open an existing engagement | ❌ **404: "upload its ledger again"** |
| Empty file / random bytes / PDF | ⚠️ rejected with 400, but messages name the internal temp file (`_upload.csv`) and raw codec errors |
| Non-UTF-8 CSV (e.g. a Windows-1252 export from Excel) | ❌ rejected. Not a fault in the file. |
| Real legacy `.xls` | ❌ advertised as supported, but `xlrd` is not installed, so it cannot be read |
| Unauthenticated access to ledger routes | ✅ 401 |
| Decision recorded, survives restart | ✅ |
| Deterministic explanation with no model | ✅ grounded, carries disclaimer |
| Report CSV/HTML | ✅ generated, HTML-escaped, disclaimer present |

---

## 3. Completed and solid (do not rebuild)

- **Canonical schema + intake mapping** for real ledger exports (Tally-style headers, derived fields, intake notice that separates file limitations from client findings).
- **Detection:** ten deterministic signals with frozen thresholds (ADR-0004), robust statistics, and Isolation Forest kept with an honest negative result (ADR-0005). The ML signal may reinforce a finding but never originate one (D-020).
- **Fusion:** transparent noisy-OR with the evidence gap as a separate uplift (ADR-0006). Removing evidence costs 30 points of precision@25. This is the central research result and it reproduces.
- **Explanation:** a provider protocol (`none` / Ollama) with a loopback check, a facts-only prompt, a guard that rejects unsupported numbers and conclusion language, and a deterministic fallback that is a first-class path.
- **Review trail:** append-only SQLite, rejection requires a reason, undo is a further decision, and the reviewer is taken from the session.
- **Accounts:** scrypt hashing, signed httponly cookies, invite code required from the first account when configured.
- **Benchmark:** held-out seeds, decoys, ablation, refuses to score on development ledgers.
- **Self-hosted Docker:** non-root, loopback-bound, API not published, health check.
- **Workspace UI:** ranked queue, filters, keyboard shortcuts, evidence drawer, toasts with undo, skeletons, reduced-motion support.

---

## 4. Gaps, ranked

Severity scale: **S1** blocks real use or is a security fault · **S2** materially hurts trust or usability · **S3** polish.

### 4.1 Critical bugs (S1)

| # | Issue | Evidence | Fix |
|---|---|---|---|
| B1 | **Uploads over 10 MB fail through the UI** | Next.js log: "Request body exceeded 10MB… socket hang up"; 500 after 30 s | Raise the proxy body limit to match the API's limit (`experimental.proxyClientMaxBodySize`, to be verified against Next 16.3 docs). Add an end-to-end test that uploads through Next, not just to the API. |
| B2 | **Analysis blocks the whole server** | Health took 12 s during a 13.5 s analysis | Run parsing and analysis off the event loop as a background job with a status endpoint. The UI polls and shows progress. |
| B3 | **Engagements are lost on restart** | Listed, but opening one returns 404 | Store the original file (see §4.3). Re-analyse on demand from the stored original. Deterministic analysis means identical findings. |
| B4 | **Shared temp filename** `data/_upload{suffix}` | `api/app.py` upload handler | Use a per-request unique temp file (and, after §4.3, the content-addressed store). Today it is masked only by B2's blocking. |
| B5 | **Critical/high npm advisories** | `npm audit` | Pin `next` to ≥ 16.3.6 (stays on 16.3 LTS); `npm audit fix` for sharp and source-map-js. |
| B6 | **`data/session.key` is tracked in git** | committed in `ffe62c1`; **not yet pushed** (local `main` is 15 ahead of the public `origin`) | Untrack it, add to `.gitignore`, and rotate the local key. Done in the audit commit; see the journal. |

### 4.2 Intake and error handling (S2)

- **E1** Non-UTF-8 CSVs are rejected. Try UTF-8-SIG, then CP1252 / UTF-16, and record which encoding was used in the intake notice.
- **E2** `.xls` is advertised but unreadable. Either add `xlrd` (BSD, small) or stop advertising `.xls`. **Recommendation:** add it, because Tally and older client exports still produce `.xls`.
- **E3** Error messages leak internals (`_upload.csv`, codec text, bare exception strings from the analysis catch-all). Map them to plain messages that state:
  - what was received;
  - what is supported;
  - what to do next;
  - that nothing was saved.
  
  Log the technical detail server-side with an error ID.
- **E4** There is no partial-processing disclosure in the UI. `rows_read`/`rows_used` exist in the API but are not prominent. Show "8,916 of 9,000 rows used, 84 had no voucher number or date", with a downloadable list of the dropped rows.
- **E5** Multi-sheet workbooks are rejected outright. Let the user pick the sheet.

### 4.3 Source documents and traceability (S1 — explicitly required)

Today, uploaded files are **"read, analysed, never stored"** (`docs/deploy.md`), and intake drops the original row index (`reset_index(drop=True)`). So:
- a finding cannot be traced to *row N of ledger.xlsx*;
- "Download Original" is impossible;
- a restart loses the engagement (B3).

**Design (smallest thing that works):**
- **Store:** `data/sources/<sha256>` holds the exact uploaded bytes, never modified, with owner-only permissions. Content-addressed, so a repeat upload is stored once.
- **Schema v2 migration:** add a `source_files` table (id, engagement_id, original filename *as metadata only*, media type, size, sha256, uploaded_at, uploaded_by, status, rows_read, rows_used, error). The existing store refuses mismatched schema versions, so this needs a real, tested v1→v2 migration.
- **Traceability:** carry `source_row` (spreadsheet row number, header-adjusted) and `source_file_id` through normalisation onto every line. A finding then reads: Finding → voucher → lines → `ledger.xlsx`, row 1,842.
- **Endpoints:**
  - list source files per engagement;
  - `GET …/original`: exact bytes, `Content-Disposition: attachment`, a safe ASCII filename, `X-Content-Type-Options: nosniff`, and a sha256 check before sending;
  - `GET …/preview?offset&limit`: first rows as JSON for CSV/XLSX, rendered as a table. No in-browser rendering of the raw file, so no XSS surface.
- **Delete:** delete an engagement's stored file(s) and cached analysis. The decision trail is kept by default, because SA 230 documentation must survive. Exact behaviour depends on **FD-2**.
- **UI:**
  - a "Source documents" panel on the engagement;
  - on each finding, "Source: ledger.xlsx · rows 1,842–1,843 · View in file / Download original".

### 4.4 Explain Finding (S1 — the priority feature)

What exists is honest but thin. Measured against the founder's spec:

| Spec | Today | Gap |
|---|---|---|
| A. What was flagged | voucher ID, date, amount | **No lines:** account names, Dr/Cr, narration, party/cost centre, preparer, approver, document ref, voucher type, posting time are all in the data but not exposed. Accounts appear as bare codes ("5700 and 2400"). |
| B. Why, with calculation | per-signal reason + evidence dict | The amount outlier has deviations and a threshold, but **no account median, typical range or count of comparable entries**. These are deterministic and cheap to add. |
| D. Contribution | "81% / 68% / 53% / 2%" | These are weighted strengths, not shares, so they sum past 100% with no label. Show contribution as High/Medium/Low **plus** the exact figure with a one-line "how priority is computed" tooltip. **The ML chip shows on most high-risk rows despite contributing ~2%**, which visually overstates a layer ADR-0005 found adds nothing. Order chips by contribution and de-emphasise anything under a floor. |
| E. Evidence availability | has / missing booleans | Distinguish **present / missing / not expected** (approval below the delegation limit) / **not in this file** (the column was absent at intake). Today a ledger with no document column makes every voucher look undocumented in the finding itself; only the intake notice warns. Show it as "Evidence: 1 of 3 expected items present". |
| C/H. Evidence and historical context | none | **Similar transactions:** deterministic. Same account (pair), nearest amounts, same party, ranked, top 3–5, each linked. No embeddings, no vector DB. |
| F. Suggested next step | none | Per-signal templates written as review procedures, not conclusions. Example: "Obtain the supporting invoice and compare with the 3 similar entries below." These are deterministic text tied to the signal kind, and each is mapped to its public SA 240 / SA 520 characteristic with a citation in docs. |
| G. Limitation | disclaimer at the end | Keep, and make it visible near the top in a single calm line. |
| Guard | numbers + forbidden phrases | **No omission check.** The prompt asks the model to mention every concern, but nothing enforces it. Add a check that each signal kind is referenced, so a model that drops a concern falls back. Also add the new facts (account names, comparables) to `structured_facts` so the guard can verify them. |
| Deep link | drawer only | Add `/review/[id]/finding/[voucher]` so a finding can be linked, refreshed and printed. |

The explanation becomes a **structured card first**, built entirely from deterministic facts:
- What · Why (signals with their working) · Evidence · Similar · Next step · Source · Trail.

Prose from the model is optional, added on top. The LLM never becomes the place where the facts live.

### 4.5 Review workflow, dashboard, reports (S2)

- **R1 — "Accept" is ambiguous.** In code it means *"agrees this needs following up"* (an exception). A CA will naturally read "Accept" as "the transaction is accepted". This is how a wrong conclusion enters an audit file. See **FD-3**.
- **R2 — Dashboard.** Engagements all show the same derived name ("ACME-IN FY2024-25"), with no date, progress, high-priority count or status. Add progress, last activity and the source file. Let the reviewer rename an engagement.
- **R3 — Search and filters:** voucher, amount, account, party, narration text; filter by signal and by evidence state.
- **R4 — Notes** on any decision (they exist in the API), shown in a per-finding trail timeline.
- **R5 — Report:**
  - separate **System finding** from **Reviewer decision** sections;
  - include the source file name + sha256, ruleset/threshold version, selection criteria and generation time (the SA 230 documentation elements);
  - add a print stylesheet so it saves cleanly as PDF from the browser. No PDF library.
- **R6 — Engagement visibility.** Today every signed-in user sees every engagement. That is right for a single firm's self-hosted install (a shared practice workspace). On a public demo it would show one visitor's uploads to another. **Default:** firm-shared when self-hosted; per-user isolation when `CAGUARD_DEMO=1`.

### 4.6 Security and privacy (S1/S2)

| # | Issue | Fix |
|---|---|---|
| S1 | Session key tracked in git (B6) | Untracked and rotated in the audit commit |
| S2 | Cookie `Secure` flag decided from the scheme the *backend* sees, which is always HTTP behind the Next proxy, so it is never set on a hosted HTTPS deployment | Trust `X-Forwarded-Proto` only from the loopback proxy, or set `CAGUARD_SECURE_COOKIES=1` on hosted deployments |
| S3 | No login throttling | In-process per-account + per-IP backoff (no Redis). Enough for one-process deployments. |
| S4 | `/api/health` is public and reveals `engagements_loaded` | Return only status + demo mode publicly |
| S5 | Whole upload read into memory before the size check | Stream to a temp file with a running byte count; reject early |
| S6 | Stored originals become sensitive data at rest (new, from §4.3) | Owner-only permissions, never served by filename, never logged, deletable. Document the data lifecycle (upload → store → analyse → finding → report → download → delete) in `08_SECURITY_PRIVACY.md`. Replace "never stored" wording **everywhere it appears in UI and docs**. |
| S7 | No CSP / security headers on the workspace | Add CSP, `frame-ancestors 'none'`, `nosniff` and `Referrer-Policy` via Next config |
| S8 | No structured logging; errors not correlated | Metadata-only logs: engagement ID, row counts, durations, finding counts, error IDs. **Never** narration, names or amounts. Test that a sample ledger's narration never appears in logs. |

The existing guarantees, including "analysis runs with every socket blocked" and the model being loopback-only, must keep passing.

### 4.7 Research and documentation (S3)

- `docs/RESULTS.md` reproduces. Keep the negative ML result visible. Do not tune the ML layer to look useful.
- Map each signal to the public SA 240 journal-entry characteristics, with citations, framed as review heuristics.
- `03_PATENT_AND_IP.md`: add newly found prior art:
  - MindBridge's per-transaction "control points" with weighted scores. This is the closest public analogue to per-signal contribution display.
  - ICAI's own AI initiatives (CA GPT, the Sarvam partnership).

  The claimed mechanism (evidence gap as a separate uplift in fusion) is unaffected so far. Still **a patent candidate, nothing more**.
- **DPDP:** core duties apply from 13 May 2027 (Rules notified Nov 2025, as reported by law-firm summaries; verify before relying on them). Storing originals strengthens the local-only argument (the vendor holds nothing) but makes the firm's own retention policy matter.
- **CA validation pack** (Phase 1): still unreviewed by a practising CA. This remains the main outside check on realism.

### 4.8 Deployment (blocker → FD-1)

Research on 2026-10-07, from official Netlify docs:
- **Netlify cannot run CA-Guard's backend.** Functions support JS/TS/Go only, with no Python runtime, no Docker and no persistent disk.
- Proxied requests time out at **26 s**.
- When free-plan credits run out, **all the team's sites are paused**.

Netlify *can* host the Next.js frontend and proxy `/api/*` to a backend hosted elsewhere. That backend still needs a host with a persistent volume, and none of those is free:
- Railway Hobby: $5/month.
- Fly.io: about $3.69/month plus a volume.
- Render free and Koyeb free have no persistent disk.
- Hugging Face Docker Spaces now need PRO.

The project constitution (constraint 5) names Railway as the demo target, and `railway.json` is already prepared.

---

## 5. Implementation phases

Each phase ends with:
- ruff, pyright and pytest clean, plus tsc, the web build and `npm audit`;
- docs and a journal entry;
- a focused commit.

Phases 1–8 need no founder input except where marked.

### Phase 1 — Critical fixes (B1–B6, S2–S5, E1–E3)
**Acceptance:**
- a 26 MB / 100k-line ledger uploads **through the workspace** and returns findings (proven by a new test through the Next server);
- `/api/health` responds in < 200 ms during an analysis;
- two simultaneous uploads both succeed with correct, distinct results;
- a CP1252 CSV and a real `.xls` file ingest;
- no error message names an internal file or shows a raw exception;
- `npm audit` is clean;
- the `Secure` cookie is set behind an HTTPS proxy (tested);
- the 6th rapid failed login is throttled.

### Phase 2 — Source documents and traceability (§4.3) — *retention behaviour per FD-2*
**Acceptance:**
- the downloaded original is **byte-identical** to the upload (sha256 asserted in tests, for CSV, XLSX and Parquet);
- after a restart, an engagement opens without re-uploading and produces identical findings;
- every finding line shows its source file and row number, and that row in the preview matches;
- v1→v2 migration is tested on a copy of a real v1 database, keeping decisions intact;
- delete removes the stored file (asserted on disk);
- a path-traversal filename cannot influence any path;
- the preview never renders raw HTML.

### Phase 3 — Explain Finding (§4.4)
**Acceptance:**
- for every signal kind, the finding card shows: transaction lines with account names and Dr/Cr; the signal's working (with comparison group and counts where applicable); a labelled contribution; the evidence state (present / missing / not expected / not in file); similar transactions; a suggested review step; the source location; the limitation;
- no field on the card is computed by the LLM;
- the guard rejects an explanation that omits a concern (test);
- the explanation still renders in full with the model off, the model timing out, or the model returning invented numbers (tests for each);
- the deep link survives a refresh;
- the ML chip no longer appears where its contribution is below the display floor.

### Phase 4 — Review workflow, dashboard, report (§4.5) — *terminology per FD-3*
**Acceptance:**
- decision labels cannot be misread (founder-approved wording);
- the dashboard shows each engagement's progress, high-priority count, source file and last activity;
- search finds a voucher by amount, account or narration in under 300 ms on 36k vouchers;
- the report shows system finding vs reviewer decision separately, plus source hash and ruleset version, and prints cleanly to PDF;
- demo mode isolates engagements per user (test).

### Phase 5 — Async analysis and observability (B2 completion, E4, S8)
**Acceptance:**
- the upload returns immediately with a job ID;
- the UI shows stages (reading → mapping → analysing → ranking) and the final row disclosure;
- a failed analysis keeps the stored file and offers a retry;
- logs record durations and counts for every stage;
- a test proves ledger contents never reach the log file.

### Phase 6 — Security and privacy review (§4.6)
**Acceptance:**
- a written threat model and data-lifecycle table in `08_SECURITY_PRIVACY.md`;
- CSP and security headers verified in responses;
- every "never stored"/"nothing uploaded" claim corrected;
- all existing privacy tests still pass, plus new ones for stored originals;
- a `/security-review` pass with findings resolved or recorded.

### Phase 7 — Test and reliability sweep
**Acceptance:** browser-level end-to-end tests drive the full path: upload → findings → open finding → explain → evidence → view/download original → decide → report. Playwright is a dev-only dependency, justified because B1 was invisible to API-level tests.

Also covered:
- malformed, empty, duplicate, huge and unsupported files;
- model missing / slow / lying;
- a database that is locked or unwritable;
- restart mid-review;
- three persona walkthroughs (experienced CA, junior auditor, non-technical accountant), written up with fixes applied.

### Phase 8 — UX polish
**Acceptance:**
- consistent terminology and spacing;
- empty, loading and error states on every screen;
- keyboard paths documented;
- an axe audit with no serious or critical issues;
- usable at tablet width;
- no gratuitous animation.

### Phase 9 — Deployment — *blocked on FD-1*
**Acceptance:**
- the self-hosted Docker image is rebuilt and verified end to end;
- the hosted demo is deployed per FD-1 with `CAGUARD_DEMO=1`, an invite code, a persistent volume and HTTPS-only cookies;
- the environment variables are documented.

### Phase 10 — Production smoke test
**Acceptance:** the full checklist from the founder's brief is run against the **live** URL, recorded in `docs/deploy.md` with date, time and results. Only then is it called "deployed".

---

## 6. Founder decisions

**Answered 2026-10-07 21:25 IST** — see D-053, D-054, D-055 in `DECISION_LOG.md`:
- **FD-1 → Railway only.** Netlify is not used. Phase 9 needs your Railway account at that point.
- **FD-2 → Keep originals until deleted, everywhere** (no automatic expiry on the demo either).
- **FD-3 → "Exception — follow up" / "Cleared — not a concern" / "Investigate".**

The options as originally put:

| ID | Decision | Blocks | Recommendation |
|---|---|---|---|
| **FD-1** | Hosting for the public demo, given Netlify cannot run the backend | Phase 9 only | **Railway Hobby ($5/mo) for the whole app**, using the config that already exists. Netlify-front + paid-backend doubles the moving parts, adds a 26 s proxy timeout and still costs money. A free Netlify *static* showcase (landing page + recorded walkthrough) is possible as an add-on. |
| **FD-2** | How long stored original files are kept | Phase 2 delete behaviour | **Keep until the reviewer deletes the engagement** (self-hosted; matches SA 230's 7-year retention being the firm's policy, not ours). On the demo, **auto-delete after 7 days**. Deleting an engagement removes the file but keeps the decision trail. |
| **FD-3** | Decision wording | Phase 4 labels | **"Exception — follow up"** (was Accept) · **"Cleared — not a concern"** (was Reject, reason required) · **"Investigate"**. Stored values unchanged, so no data migration. |

**Optional founder action:** get the CA validation pack (`docs/ca_validation/`) reviewed by a practising CA. It is not blocking, but it is the strongest outside check available.
