# CA-Guard — Claude Code Project Constitution

## Mission
CA-Guard is a focused 3-month academic/research/startup prototype for Indian Chartered Accountants and accountants. It is a privacy-preserving, locally deployable hybrid AI review assistant that analyzes financial journal/transaction data, prioritizes unusual items, retrieves evidence, explains findings, and keeps final professional judgment with the human reviewer.

Long-term vision: CA-OS. Current scope: CA-Guard only.

## Operating principle
Research → validate → design → plan → implement → test → fix → document → commit → proceed.
Never skip a gate.

## Non-negotiable constraints
1. Do not turn this into a general ERP, tax filing platform, GST filing platform, autonomous auditor, or Tally replacement.
2. Do not train an LLM from scratch.
3. Do not use proprietary or paid APIs/services when a free/open-source alternative is practical.
4. External LLM calls must NOT receive real client financial data. The product's privacy story is local/on-premise by design.
5. Railway is for the public demo deployment only. Do NOT claim the Railway deployment is on-premise/private. The private product path must be self-hostable.
6. Neon is optional and only for demo metadata/auth/config if needed. Real client financial data should not depend on Neon in privacy mode.
7. If credentials, paid services, unverifiable legal material, or a material founder decision is required, stop and ask the user. Do not fabricate credentials or silently choose a costly service.
8. Use synthetic/public data only until a formal privacy-safe customer-data plan exists.
9. Every implementation phase must finish with tests, bug fixing, a clean working tree, documentation, and a Git commit.
10. Never claim "patentable" or "patent granted". Say "patent candidate" and keep an explicit prior-art/claim-risk record.
11. No destructive git commands, force pushes, secret commits, or broad dependency upgrades without a clear reason.

## Product truth
The LLM explains structured findings. It must not be the sole numerical anomaly detector or source of accounting truth.

Preferred pipeline:
financial data → normalization → deterministic/rule checks + statistical checks + ML anomaly signals → risk fusion → evidence retrieval → grounded explanation → human review.

## Quality bar
Write production-style modular code. Prefer small cohesive modules, explicit contracts, type validation, testable pure functions, deterministic evaluation, observability, and clear error handling.

Every phase must add or update:
- implementation
- unit tests
- integration tests where applicable
- end-to-end smoke coverage where applicable
- docs / ADRs when a material decision is made
- journal.md entry
- Git commit

## UI/UX bar
Build a polished professional finance/audit application, not a generic dashboard. Use open-source/customized shadcn/ui patterns and research 21st.dev for layout inspiration. Micro-animations should be purposeful and subtle. Do not require a paid 21st.dev subscription for the finished product.

## Dataset policy
Primary external benchmark candidate: VynFi/vynfi-journal-entries-1m (synthetic journal-entry data, Apache-2.0 according to the project README). Because the benchmark is not India-specific, also create a project-owned, reproducible synthetic Indian-style journal dataset with controlled injected anomalies and known ground truth. Claude must re-verify the dataset license/availability before any ingestion code is written.

Do not use the 2026 SSRN "Generating Synthetic Journal Entries for Audit Analytics" dataset as a redistributable project dependency: the SSRN page states reuse is not permitted without permission.

## India audit alignment
Use public ICAI material only as guidance and cite sources in docs. The initial rule set should be framed as audit-review heuristics, not legal/accounting advice. SA 240 provides relevant journal-entry characteristics for fraud consideration; SA 520 covers analytical procedures; SA 530 covers audit sampling. Validate exact current applicability before release.

## Current external facts to verify at the start of work
- IP India published 2025 CRI Guidelines and 2026 AI patent-examination guidance.
- Railway has a $0 Free plan with limited credits; Hobby is $5/month according to current pricing. Do not assume free hosting forever.
- Next.js 16.3.x is active LTS as of the latest August 2026 security release.
- Claude Code supports CLAUDE.md, auto memory, hooks, MCP, and skills. Use these deliberately, not excessively.

## Session start protocol
At the beginning of every substantial Claude Code session:
1. Read this file.
2. Read docs/00_PROJECT_CHARTER.md, docs/01_RESEARCH_BRIEF.md, docs/05_TECH_STACK.md, docs/11_IMPLEMENTATION_ROADMAP.md, and journal.md.
3. Inspect git status and recent history.
4. Reconcile the current phase with the roadmap.
5. Before coding, check whether the current phase has a research/design gate that is incomplete.

## Completion protocol
Before declaring any phase complete:
1. Run formatter/linter/type checker.
2. Run relevant unit/integration/E2E tests.
3. Run security/static checks available for the stack.
4. Fix failures, rerun tests, and only then proceed.
5. Update journal.md with a human-readable timestamped entry.
6. Update relevant docs/ADRs.
7. Inspect git diff and git status.
8. Commit with a clear Conventional Commit message.
9. Report commit hash, tests run, outcome, and anything that needs founder input.

## Founder decisions
Use the following labels in journal.md:
- [FOUNDER DECISION] — user must decide
- [CREDENTIALS NEEDED] — user must provide a secret/key/account action
- [RESEARCH NEEDED] — Claude should investigate before proceeding
- [BLOCKED] — cannot safely proceed
- [DECIDED] — decision recorded and binding until changed

## Do not over-engineer
Prefer the smallest architecture that supports the research hypothesis and an excellent demo. Avoid microservices unless proven necessary. Avoid Kubernetes, Kafka, vector databases, complex agent swarms, paid OCR, and unnecessary cloud infrastructure.
