# Technology Stack Decision

## Principle
Use a simple, free, widely supported stack that Claude Code can build quickly and students can maintain.

> **Frozen 2026-09-06 (Phase 0, ADR-0002).** Verified by actually installing and importing the stack, not by reading metadata. Binding hardware constraint discovered: **8 GB unified memory, arm64** — this caps the local model at 3–4B, not 7B.
>
> | Layer | Frozen choice |
> |---|---|
> | Frontend | Next.js **16.3.4** (Active LTS to 2027-10-22), TypeScript, Tailwind v4, shadcn/ui (MIT, vendored) |
> | Backend | Python **3.13** (3.14.3 verified as fallback), FastAPI 0.141.1, Pydantic 2.13.5 |
> | Dataframes | **pandas 3.0.5 — Polars rejected.** 34 MB / 667k rows does not justify a second engine. |
> | ML | scikit-learn 1.9.0 (Isolation Forest) |
> | Storage | SQLite for local/private; Postgres only if the demo requires it |
> | Local LLM | Ollama + a **3–4B** instruct model (Qwen3.5-4B / Phi-4-mini / Gemma-4-E4B) — **not 7B** |
>
> **Railway cost reality:** the $0 Free plan is 1 vCPU / **0.5 GB RAM** / 1 replica with $1 monthly credit — it **cannot** host this stack. A working public demo needs **Hobby at $5/month**. Neon's free tier (0.5 GB, 100 CU-hours, 5-min auto-suspend) is permanent and adequate if ever needed, but the private path must not depend on it.

## Proposed stack

### Frontend
- Next.js 16.x (current active LTS line at the project start)
- TypeScript
- Tailwind CSS
- shadcn/ui components
- Lucide icons
- Motion/Framer Motion only where useful and free

### Backend
- Python 3.12+ or the currently supported stable Python version validated during Phase 0
- FastAPI
- Pydantic
- pandas or Polars (choose after benchmarking)
- scikit-learn
- openpyxl

### Data/storage
- Local file/SQLite for zero-persistence/local demo mode where possible.
- PostgreSQL only for application metadata when needed.
- Neon PostgreSQL is permitted for the Railway demo, but not required for private financial-data processing.

### AI
- Prefer a small local/open-weight instruct model for explanation in the self-hosted path.
- Do not call a cloud LLM with real client financial data.
- Detection must work even when the LLM is unavailable.

### Packaging/deployment
- Docker
- Railway for public/demo deployment
- Self-hosted Docker Compose path for the private deployment story

## Why this stack
It minimizes moving parts while still giving:
- a polished web UI;
- a strong Python analytics layer;
- reproducible local deployment;
- a clean path to Railway;
- free/open-source tooling.

## Important deployment reality
Railway is cloud infrastructure. Therefore the public deployment is a demonstration environment and should use synthetic/public data. The privacy-preserving product claim applies to the self-hosted/on-premise deployment path.

Sources:
- Next.js security/LTS updates: https://nextjs.org/blog
- FastAPI containers: https://fastapi.tiangolo.com/deployment/docker/
- Railway pricing: https://docs.railway.com/pricing
