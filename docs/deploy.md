# Running CA-Guard

Two paths, and they are not the same product.

| | **Self-hosted** | **Public demo** |
|---|---|---|
| Where | A firm's own machine | Cloud infrastructure |
| Data | Real client ledgers | **Synthetic only** |
| Privacy claim | Nothing leaves the machine | None — it is a demonstration |
| Cost | ₹0 | Monthly hosting |
| Status | ✅ Built and tested | ✅ **Live** at <https://ca-guard-production.up.railway.app> (deployed and verified 2026-10-08 02:22 IST) |

The distinction is not marketing. D-005 exists because calling a cloud-hosted demo "on-premise" would be untrue, and a CA relying on that sentence would be misled about where their client's data sits.

---

## Self-hosted — the actual product

### With Docker (recommended)

```bash
docker compose up --build
```

Then open **http://127.0.0.1:3000**.

That is the whole installation. No account, no key, no card, no external service.

### What the container does and does not do

- Runs as an unprivileged user (`uid 10001`), never root.
- Binds the workspace to **loopback only**. Publishing on `0.0.0.0` would put a client's ledger on the office network; the compose file is written that way deliberately, and changing it is a decision to make consciously and with authentication in front.
- **Does not publish the analysis API at all.** It listens on `127.0.0.1:8000` *inside* the container. A reviewer reaches the workspace; the workspace reaches the API. A mistaken port mapping cannot expose the ledger endpoints.
- Needs no network for analysis. `tests/test_security.py::test_analysis_needs_no_network` proves it by making every socket call raise and running the whole pipeline anyway.

### Where the data lives

| | |
|---|---|
| **Uploaded ledgers (originals)** | `/data/sources/<sha256>.<ext>`, byte-for-byte, owner-only permissions. Kept until an administrator deletes them (D-054). |
| Source file records | `/data/review.db` (name, size, fingerprint, who uploaded it, when) |
| Findings | Recomputed from the stored original; never stored themselves |
| **Review decisions and the audit trail** | `/data/review.db` in the `caguard-data` volume |

**Back up that volume.** It holds the decisions, which cannot be recomputed, and the client's original files. Treat the backup as you would the client's books: it *is* a copy of them.

**Deleting a client's file.** In the workspace, open the engagement → **Source** → **Delete** (administrators only). The bytes are removed from disk; the record that the file existed, and every decision made on it, are kept for the audit trail.

```bash
docker run --rm -v caguard-data:/data -v "$PWD:/backup" alpine \
  tar czf /backup/caguard-decisions-$(date +%F).tar.gz -C /data .
```

### Without Docker

```bash
make install          # dependencies
make serve            # the API on 127.0.0.1:8000
make web-install
make web              # the workspace on 127.0.0.1:3000
```

### Optional: local explanations

CA-Guard writes its own explanations and needs nothing installed — that is the default and it is complete. A local model only changes the wording.

```bash
make model-check      # will this machine take it?
make model-install    # Ollama + Qwen3 1.7B, free, ~1.4 GB
docker compose up --build -e CAGUARD_MODEL=qwen3:1.7b
```

The model runs on the same machine, is checked against loopback at construction, and is never sent a ledger row — only the verified facts of a single finding. See `docs/adr/0007-local-model-strategy.md`.

---

## Operating it

### Upgrading

```bash
git pull && docker compose up --build -d
```

Decisions survive: they are in the volume, and the schema version is checked on open. If a future build expects a different schema, CA-Guard refuses to open the file rather than guessing.

### Checking it is healthy

```bash
docker compose ps                       # the container reports its own health
curl -s http://127.0.0.1:3000/api/health
```

### If something goes wrong

| Symptom | Where to look |
|---|---|
| Upload rejected | The message names what was missing. `caguard columns <file>` shows how the headers mapped. |
| Findings look wrong for the client | Read the intake notice at the top of the queue — a missing column makes every entry look undocumented. |
| Workspace loads but shows nothing | `docker compose logs caguard` |
| Explanations say "Written by CA-Guard" | No model installed. That is the default and is not a fault. |

---

## Public demo on Railway

**Live**, after being prepared and verified locally (2026-10-08 01:52 IST). Deploying needs the founder's Railway account (sign-in is interactive) and the Hobby plan. Once the CLI on this machine is signed in, the steps below are run by Claude.

### The image, verified as Railway will run it

| Check | Result |
|---|---|
| Dependencies | Installed from `uv.lock` with `uv sync --frozen`; no uv, compilers or caches in the final image |
| Runtime user | uid 10001; the app code is read-only to it; only `/data` is writable |
| Node | The exact version the workspace was built with (copied, not the distribution's package) |
| Health | Checked *through* the workspace, so healthy means both processes serve |
| A process dies | The container exits (verified by killing the engine: exit 137), so Railway's `ON_FAILURE` policy restarts it |
| Restart with a volume | Account, engagement (rebuilt from its stored original) and decisions all survive |
| Demo mode | An invite code under 16 characters stops start-up with a clear message; sign-up without the code is refused; API docs are hidden |

### What is already in place

| | |
|---|---|
| `railway.json` | Builds the Dockerfile, health-checks `/api/health` |
| Port | Next reads Railway's `$PORT` itself — no `$PORT` in a start command, which Railway would not expand |
| The analysis API | Stays on loopback **inside** the container. Only the workspace is ever reachable. |
| Authentication | Every ledger route requires a signed-in account |
| **Bootstrap protection** | With `CAGUARD_INVITE_CODE` set, even the *first* account needs it — closing the window between going live and you signing up |
| **Demo banner** | With `CAGUARD_DEMO=1`, every page says it is a demonstration on synthetic data |
| **Visitor isolation** | With `CAGUARD_DEMO=1`, each account sees only its own engagements, even when two visitors upload the same sample file (D-060) |

### The settings you must add

| Variable | Value | Why it matters |
|---|---|---|
| `CAGUARD_DEMO` | `1` | Shows the banner. **Required.** Without it the page implies a privacy claim that is not true of hosted infrastructure (D-005). |
| `CAGUARD_INVITE_CODE` | at least 16 random characters — generate with `python -c "import secrets; print(secrets.token_urlsafe(18))"` | Stops strangers creating accounts, including the first one. **Required.** CA-Guard refuses to start with a shorter one. |
| `CAGUARD_SECURE_COOKIES` | `1` | **Recommended on Railway.** CA-Guard already marks the session cookie Secure when the proxy reports HTTPS; setting this removes any doubt on a hosted deployment. Never set it on a plain-http local install, or sign-in will stop working. |
| `CAGUARD_STORE` | `/data/review.db` | Already the default; set it if you mount the volume elsewhere. |

### A volume is not optional

Railway containers have ephemeral disks. **Without a volume mounted at `/data`, every review decision is lost on each redeploy** — and the decisions are the only thing in the system that cannot be recomputed.

### Cost

**Hobby, $5/month.** The free plan gives 1 vCPU and 0.5 GB of RAM; this stack will not run in that.

### What Claude runs once the CLI is signed in

```bash
railway init --name ca-guard-demo            # the project
railway up --detach                           # build the Dockerfile and deploy (railway.json)
railway volume add --mount-path /data         # decisions and stored originals survive redeploys
railway variable set CAGUARD_DEMO=1 CAGUARD_SECURE_COOKIES=1
railway variable set CAGUARD_INVITE_CODE="$(python -c 'import secrets; print(secrets.token_urlsafe(18))')"
railway domain                                # a public https://…up.railway.app address
railway logs                                  # read, don't guess, if anything fails
```

The invite code is generated straight into Railway and never printed into this repository or the journal. To read it: `railway variables`, or the service's **Variables** tab in the Railway dashboard.

### Live verification (2026-10-08 02:22 IST)

Run against the live URL after deployment.

**Without an account — 23 of 23 pass:**
- HTTPS health, reporting demo mode;
- pages and deep links load;
- CSP, HSTS, `nosniff` and DENY framing are present;
- every ledger route returns 401;
- sign-up is refused without the invite code, and with a wrong one;
- no API docs;
- no secrets in the browser scripts;
- the demo banner text is shipped.

**Signed in, as a throwaway test account — 17 of 17 pass:**
- the cookie is Secure, HttpOnly and SameSite=Lax;
- the sample ledger runs as a background analysis (3.9 s; 82 findings of 1,533 vouchers);
- the explanation card, transaction lines with source rows, and the deterministic written explanation;
- a decision recorded and persisted;
- the original download is byte-identical;
- the report separates observed from decided, under a strict CSP; the CSV downloads;
- in a real browser: the demo banner, a deep link, and zero console errors.

**Persistence:** after a redeploy, the account, engagement and decision survived on the volume.

**Reset for handover:** the volume holding the test data was replaced with an empty one, and the service redeployed. The site then reported `any_users: false`, and the test login was rejected. The first person to sign up with the invite code becomes the administrator.

**Lessons from deploying:**
- Railway rejects `VOLUME` in a Dockerfile. The error appears in the dashboard's build log, not the CLI's.
- Railway volumes are mounted root-owned; the entrypoint hands `/data` to the app user and then drops all privileges.
- Railway injects `PORT` (8080 here). The domain targets that port; nothing hard-codes 3000.
- The trial volume is **500 MB**. The Hobby plan allows more. Stored originals count against it.

### After it is live

1. **Sign up immediately**, using the invite code, so the administrator account is yours.
2. Generate a demonstration ledger locally with `caguard generate` and upload that.
3. **Never upload a real client ledger.** The banner says so; it is on you as well.

---

## Why the two paths stay separate

A local Docker demonstration with a screen recording costs nothing and shows the
same product — and for a faculty review it is arguably the more honest artefact,
because a local install *is* what CA-Guard is designed to be. A hosted demo buys
one thing the recording cannot: somebody can try it themselves without
installing anything.

Both are legitimate. What is not legitimate is letting the hosted one imply the
privacy claim that belongs to the other, which is why the banner is not optional.
