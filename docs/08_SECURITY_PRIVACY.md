# Security and Privacy

## Privacy model
The product is designed around local/self-hosted processing. Do not send real client data to external AI services.

## Data minimization
- process only required columns;
- redact or hash identifiers where practical;
- never put raw financial rows in application logs;
- default to short-lived working files;
- allow configured retention mode;
- provide a zero-persistence processing path where technically feasible.

## Important distinction
“Not used to train the model” is not the same as “never left the firm.” CA-Guard’s strongest privacy claim is achieved by keeping data local and avoiding external model calls for sensitive data.

## Railway limitation
Railway is hosted infrastructure. The demo must therefore use synthetic/public data. Do not market the Railway deployment as the private on-premise version.

## Security checks
- dependency audit;
- input validation;
- upload size/type limits;
- path traversal protection;
- safe filename handling;
- authentication for deployment where necessary;
- secret management via environment variables;
- redaction in logs;
- no secrets committed to git.

## Implemented controls (updated 2026-10-07, Phase 1 of the completion plan)

| Control | Where | Verified by |
|---|---|---|
| Upload type allow-list; the filename never becomes a path | `intake/readers.py::safe_suffix` | `tests/test_security.py` |
| Upload size limit, enforced while the upload is being received; the API, not the proxy, decides | `api/app.py::_receive`, `web/next.config.ts` | `tests/test_upload_robustness.py`, `scripts/smoke_workspace.py` |
| A unique temporary file per upload, removed on success and on every failure | `api/app.py::_receive` | `tests/test_upload_robustness.py` |
| Error messages name the user's file, never internal paths or exception text; unexpected failures carry an error reference and are logged without ledger contents | `api/app.py::_analyse_upload` | `tests/test_upload_robustness.py` |
| Analysis runs off the event loop, so one upload cannot stall the service for others | `api/app.py::upload` | `test_the_server_answers_while_a_ledger_is_being_analysed` |
| Sign-in throttling: 5 failures per account in 15 minutes, then HTTP 429 with `Retry-After`. Keyed per account, because behind the proxy every request comes from loopback. | `auth/throttle.py` | `tests/test_auth_hardening.py` |
| Session cookie marked `Secure` whenever the browser reached CA-Guard over HTTPS. `X-Forwarded-Proto` is trusted only from the loopback proxy; `CAGUARD_SECURE_COOKIES=1` forces it. | `api/auth_routes.py::reached_over_https` | `tests/test_auth_hardening.py`, smoke script |
| The public health check reveals nothing about workload | `api/app.py::health` | `test_health_does_not_disclose_workload` |
| The session signing key is generated per installation and never committed | `.gitignore`, `auth/sessions.py` | — (key removed from tracking 2026-10-07) |
| Dependency audits: `pip-audit` + `npm audit` | `make audit`, CI | clean on 2026-10-07 after patching Next.js to 16.3.8 |

**Not yet done** (see `docs/FINAL_COMPLETION_PLAN.md`):
- CSP and security headers (Phase 6);
- structured, metadata-only logging (Phase 5);
- a data-lifecycle table once original files are stored (Phase 2).

## Data lifecycle (since 2026-10-07, D-054)

Where a client's ledger exists at each step, on a self-hosted install. On the Railway demo the same is true, but "this machine" is a hosted server, which is why the demo is synthetic-data only (D-005, D-052).

| Step | Where the data is | How long | Who can reach it |
|---|---|---|---|
| Upload in transit | Browser → workspace (Next.js, same machine) → API on loopback | Seconds | Nothing outside the machine; the API is never published |
| Receiving | `data/upload-<random>.<ext>` (0600), unique per request | Until analysis ends; removed on every failure path | The CA-Guard process |
| **Stored original** | `data/sources/<sha256>.<ext>` (0600, directory 0700). Exact bytes; re-hashed before every download. | **Until an administrator deletes it** | Signed-in reviewers via the workspace; deletion is admin-only |
| Source record | `data/review.db` → `source_files`: filename, size, SHA-256, uploader, row counts, deletion record | Kept after the file is deleted, so the trail can still say which file a decision was made on | Signed-in reviewers |
| Parsed ledger + findings | Process memory only | Until restart; rebuilt from the stored original on next open | The CA-Guard process |
| Explanation prompt | Only if a local model is configured: the finding's verified facts (no ledger rows, no narration) go to Ollama on loopback | Duration of one request | The local model process |
| Decisions and audit trail | `data/review.db` → `decisions`, append-only | Permanent; never edited or deleted | Signed-in reviewers |
| Report | Generated on request, sent to the browser; not written to disk | — | The reviewer who downloads it |
| Logs | stderr / container logs: event names, ids, counts, durations, error types. **Never ledger contents** (tested). | Per the host's log retention | Whoever operates the machine |
| Backups | Whatever the firm does with the `/data` volume. It contains the originals. | Firm policy | Firm policy |

**What CA-Guard does not do:** send a ledger, a row, a narration or a finding to any outside service. `tests/test_security.py::test_analysis_needs_no_network` runs the analysis with every socket blocked.

**Retention:** CA-Guard never deletes a file on its own. Under SQC 1 / SA 230, a firm keeps audit documentation for at least seven years. Whether a copy of the client's ledger forms part of that documentation is the firm's decision, not CA-Guard's. Under the DPDP Act, which is expected to take full effect in May 2027, the firm should also record why it keeps personal data inside ledgers, such as vendor and employee names. This is guidance, not legal advice.

## Threat model (Phase 6, 2026-10-07)

Who might attack, what they want, and what stops them. Two deployments, with different exposure.

### Self-hosted (the product)

The workspace is published on `127.0.0.1:3000` only; the API is never published. The realistic threats are on the machine itself, and from files.

| Threat | Control | Residual risk |
|---|---|---|
| A hostile file: path traversal, XML entity bomb, zip bomb, binary posing as CSV | The filename never becomes a path (allow-listed suffix, content-addressed storage). Entity bombs are refused by Python's bundled expat, which limits amplification (tested). `.xlsx` unpacked size is checked against the zip directory before parsing (1 GiB cap). Binary data in a CSV is refused. | A Parquet file crafted to exhaust memory is not specifically defended; only firm-supplied files reach a self-hosted install. |
| Someone else at the office opens the workspace | Every ledger route requires a session; passwords are scrypt-hashed; sign-in is throttled per account; sign-up after the first account needs an invite code. | Anyone with an account sees the whole firm's work — by design (shared workspace). |
| Ledger data leaks via logs | Logging goes through one redacting helper. A test runs the whole review path and searches the log for ledger text (mutation-checked). | Operators can still read the stored originals on disk — they are the firm's own files. |
| Ledger data leaves the machine | Analysis runs with every socket blocked (test). The optional model must be on loopback (checked at construction) and receives only a finding's verified facts. | None known. |
| A backup copy leaks | — | The `/data` volume holds the originals; backups are the firm's responsibility (`docs/deploy.md`). |

### Public demo (Railway, synthetic data only)

The workspace is on the internet behind HTTPS. The API stays on loopback inside the container.

| Threat | Control | Residual risk |
|---|---|---|
| A stranger creates an account | An invite code is required from the very first account (D-051). | Anyone holding the code can sign up. Rotate it if it leaks. |
| One visitor sees another's work | Engagement ids are scoped per account. All 12 engagement routes check ownership and answer 404 for "not yours" (tested and mutation-checked). | — |
| Password guessing | Five failures per account per 15 minutes, then HTTP 429. | Throttling is in-process: a restart resets the counters. Many accounts can still be tried slowly. |
| Session theft | httponly, SameSite=Lax cookies, marked Secure when the browser arrived over HTTPS (trusted only from the loopback proxy); 12-hour expiry; HMAC-signed. | No server-side revocation before expiry (logout clears the cookie; rotating the key file logs everyone out). |
| Cross-site request forgery | SameSite=Lax cookies are not sent on cross-site POST, PATCH or DELETE. No state change happens on GET. | Relies on browser SameSite support (all current browsers). |
| Cross-site scripting | React escapes all rendered text. The HTML report escapes every value and is served with `default-src 'none'` (no scripts at all). The workspace CSP allows only its own origin; `frame-ancestors 'none'`. | The workspace CSP permits inline scripts (Next's bootstrap). A nonce-based CSP would remove this. |
| Someone uploads a real client ledger to the demo | A permanent demo banner; the invite gate; the wording never claims the demo is private. | Ultimately a human decision. The banner says so. |
| Resource abuse | 200 MB upload cap; 2-worker job pool; 2 M row cap; preview pages capped at 200 rows. | No per-user upload quota. The invite gate is the limiter. |

### Independent review, 2026-10-07

A separate reviewer was given the code with no stake in its design and asked to break it. They found **no authentication bypass and no cross-engagement access**. What they did find, and what happened to each finding:

| Finding | Status |
|---|---|
| CSV formula injection in the report export (ledger text, notes and display names could run as Excel formulas) | **Fixed.** Every text cell is neutralised (`report.neutralise_formula`). The first attempt silently matched no columns under pandas 3's string dtype; the proof of concept caught it. |
| Signing out did not end the session; a copied cookie kept working | **Fixed.** Per-user session epoch in every token; signing out or changing a password ends all sessions. Old cookies read as epoch 0, so nobody was logged out by the upgrade. |
| Anonymous requests could grow the login throttle's memory | **Fixed.** Input length limits; hashed keys; expired entries swept; at most 10,000 tracked. |
| Invite codes could be guessed online, unthrottled | **Fixed.** Sign-up failures are throttled (10 per 15 min); a configured code under 16 characters stops the app at startup. |
| Parquet uploads could decode to hundreds of times their size | **Fixed by removal.** Parquet's declared sizes describe encoded data, measured at 21 KB declared vs 200 MB decoded, so no reliable pre-check exists. It stays available from the CLI only (D-065). |
| One account could exhaust memory or workers | **Fixed.** At most 2 analyses in flight per account (429 beyond); the one-request upload shares the same pool; at most 6 analyses cached, the rest rebuilt from their originals. |
| Sign-in timing revealed which addresses have accounts | **Fixed.** Unknown addresses are checked against a dummy hash. |
| Short or empty session key; key and invite files written before chmod; leftover upload files | **Fixed.** Keys under 32 bytes refused; files created owner-only with `O_EXCL`; `upload-*` swept at startup. |
| Voucher numbers interpolated into URLs unencoded | **Fixed**, and it exposed a real bug: findings whose voucher number contains "/" (Tally's "JV/2024/117") could not be opened at all. The routes now take a path parameter. |
| Per-account lockout can be triggered by someone who knows the address | **Accepted** for now. Lockout lasts 15 minutes. Revisit with exponential back-off if the demo sees abuse. |
| Dockerfile installs without the lockfile; app code writable at runtime; misleading entrypoint comment | **Phase 9**, when the image is rebuilt and deployed. |
| An `Origin` check on state-changing requests (another local service on `localhost` counts as same-site) | **Not adopted yet.** Low risk on a firm's own machine; recorded for Phase 9. |
| `.xlsx` under the 1 GiB unpacked cap may still be heavy in memory (suspected, not reproduced) | **Recorded.** The 2-worker pool and per-account cap bound how many can run at once. |

### Checked and not adopted

- **`defusedxml`**: not added. A crafted entity bomb is already refused by Python 3.13's bundled expat in 0.1 s (`tests/test_security_hardening.py`), so the extra dependency would defend against an attack already handled.
- **A nonce-based CSP**: deferred. It needs a Next middleware issuing per-request nonces. The present policy already blocks third-party script origins, framing, plugins and off-site form posts.
