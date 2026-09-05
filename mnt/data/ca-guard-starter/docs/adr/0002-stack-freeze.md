# ADR-0002 — Freeze the technology stack

- **Date:** 2026-09-06
- **Status:** Proposed

## Context
`05_TECH_STACK.md` proposed a stack with several open choices (Python version, pandas vs Polars, which local model). Phase 0 required verifying compatibility and cost against primary sources rather than assuming.

The binding constraint discovered was hardware: **8 GB unified memory on arm64**.

## Decision

| Layer | Choice | Reason |
|---|---|---|
| Frontend | Next.js 16.3.4, TypeScript, Tailwind v4, shadcn/ui | v16 is Active LTS through 2027-10-22; 16.3.4 released 2026-08-31. shadcn is MIT and copied into the repo, so no runtime dependency on a third party. |
| UI inspiration | 21st.dev, browse-only | MIT, free tier. No paid dependency enters the repo. |
| Backend | Python 3.13, FastAPI, Pydantic v2 | Verified by actually installing and importing the full stack on 3.13.1 **and** 3.14.3. 3.13 pinned for Docker/CI wheel breadth. |
| Dataframes | pandas 3.0.5 — **not** Polars | 34 MB / 667k rows does not justify a second engine. Polars lacks a 3.14 classifier. One engine, fewer failure modes. |
| ML | scikit-learn 1.9.0, Isolation Forest | Verified; sufficient for the hypothesis. |
| Storage | SQLite for local/private; Postgres only if the demo demands it | Keeps the private path free of cloud dependencies (D-006). |
| Local LLM | Ollama + a **3–4B** instruct model | **Forced by 8 GB RAM.** A 7B Q4 model (~4.5 GB) alongside Next.js, Python, Docker and a browser will thrash. |
| Deployment | Docker Compose (private) + Railway (demo) | Railway CLI already installed locally. |

## Consequences
- The 3–4B ceiling means explanation quality will be modest. Acceptable, because the LLM only renders structured findings into prose and must never be the source of numerical truth (D-002). The deterministic fallback path is mandatory, not optional.
- Railway's $0 plan (1 vCPU / 0.5 GB / 1 replica) **cannot** host this stack. A real public demo needs Hobby at $5/month. Raised as credential/cost gate C-1.
- Neon's free tier is permanent and adequate if ever needed, but the private path must not depend on it.
