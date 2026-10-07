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
