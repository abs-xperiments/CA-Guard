# Running CA-Guard

Two paths, and they are not the same product.

| | **Self-hosted** | **Public demo** |
|---|---|---|
| Where | A firm's own machine | Cloud infrastructure |
| Data | Real client ledgers | **Synthetic only** |
| Privacy claim | Nothing leaves the machine | None — it is a demonstration |
| Cost | ₹0 | Monthly hosting |
| Status | ✅ Built and tested | ⏸ **Not built.** Awaiting a founder decision. |

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
| Uploaded ledgers | Read, analysed, **never stored** |
| Findings | Recomputed from the ledger every time |
| **Review decisions and the audit trail** | `/data/review.db` in the `caguard-data` volume |

**Back up that volume.** The decisions are the only thing in the system that cannot be recomputed.

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

## Public demo — a decision, not a default

**Nothing is deployed and nothing has been spent.** Founder direction C-1 was explicit: keep development at ₹0 and revisit hosting only once the product works. It now works, so the decision is live.

### What deploying would mean

- **Railway Hobby, $5/month.** The free plan is 1 vCPU and 0.5 GB of RAM, which will not run this stack.
- **Synthetic data only**, permanently. `caguard generate` produces the demonstration ledger.
- **A password gate is mandatory.** A public URL is public: without one, strangers can upload files and consume the machine.
- **The wording must stay honest.** The demo page has to say it is a demonstration on synthetic data, and that the privacy claim applies to the self-hosted path. That is D-005 and it is not negotiable.

### The alternative, at ₹0

A local Docker demonstration with a screen recording. For a faculty review, a conference or a portfolio, this shows the same product and costs nothing. It is also more honest, because it is the deployment the product is actually designed for.

### What is needed to proceed

A founder decision, and then a Railway account. Nothing in the repository has to change first — the image already runs, and the API already refuses non-loopback binds, so the deployment would need a deliberate configuration change rather than an accident.
