# Technology Stack Decision

## Principle
Use a simple, free, widely supported stack that Claude Code can build quickly and students can maintain.

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
