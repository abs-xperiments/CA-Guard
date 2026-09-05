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
