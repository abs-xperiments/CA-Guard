# Architecture

## Target architecture

```text
                  Reviewer
                     │
                     ▼
              ┌───────────────┐
              │  Next.js UI   │
              └───────┬───────┘
                      │
                      ▼
              ┌───────────────┐
              │ FastAPI API   │
              └───────┬───────┘
                      │
            ┌─────────┴─────────┐
            ▼                   ▼
      Intake/Normalize     Review Service
            │                   │
            ▼                   ▼
   ┌────────┼───────────┐   Evidence Store
   ▼        ▼           ▼
 Rules   Statistics     ML
   └────────┼───────────┘
            ▼
       Risk Fusion
            │
            ▼
    Evidence Retrieval
            │
            ▼
      Local/Private LLM
            │
            ▼
   Grounded Explanation
            │
            ▼
      Human Decision
```

## Source files and traceability (added 2026-10-07, D-054)

```
upload ──► data/upload-<random>  ──analyse──► success? ──► data/sources/<sha256>.<ext>  (exact bytes, 0600)
                                    │                         │
                                    └─ failure: deleted,      └─ review.db: source_files (name, size,
                                       "Nothing was saved"       sha256, uploader, rows, deletion record)

finding ─► voucher ─► lines (account, Dr/Cr, narration, …) ─► source_row ─► "ledger.xlsx, row 8,916"
```

| Module | Responsibility |
|---|---|
| `review/sources.py` | Content-addressed vault for original uploads. It re-hashes before serving. |
| `review/store.py` | SQLite at schema v2. Ordered migrations: a fresh file and a v1 file climb the same path. |
| `intake/normalise.py` | Carries `source_row` (Excel numbering, header = row 1) onto every line. It is excluded from the ledger hash, so existing engagement IDs are unchanged. |
| `api/workspace.py` | Analyses in memory. Ingest keeps the original only after a successful analysis. An engagement not in memory is rebuilt from its stored original and checked against its recorded content hash. |
| `api/source_routes.py` | List, download the original, paged preview (served as data, never rendered), and admin-only delete. Every route checks that the file belongs to the engagement in the URL. |

## Core design decision
The LLM is downstream of deterministic/ML analysis. If the LLM is off, CA-Guard still detects and ranks anomalies.

## Deployment modes
### Private/self-hosted
All sensitive inputs and analysis stay on the firm’s machine/server.

### Public demo
Railway-hosted demo using only synthetic/public data. It may use Neon for non-sensitive metadata if needed.

## Avoid
- microservice sprawl;
- Kafka;
- Kubernetes;
- external vector DB unless evaluation proves it necessary;
- paid OCR/API dependencies.
