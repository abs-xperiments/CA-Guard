# CA-Guard Journal

This journal is intentionally written so a founder/student can understand what is happening without reading the code.

## 2026-09-06 — Project bootstrap
**Status:** Research/design ready for Claude validation.

**What we are building:** A private AI second-hand for CAs/accountants that finds unusual financial transactions, explains why they matter, shows evidence, and leaves the final decision to the professional.

**What we are deliberately NOT building:** a complete CA ERP, tax/GST filing system, autonomous audit opinion engine, or Tally replacement.

**Important design decision:** The numerical detection logic should be deterministic/statistical/ML and testable. The LLM is mainly for explaining structured findings. This keeps the system more reliable and easier to evaluate.

**Privacy decision:** The real product must have a self-hosted/on-premise path. Railway is only for a synthetic-data public demo. This prevents us from making a misleading “nothing leaves the office” claim about a cloud-hosted demo.

**Dataset direction:** Use a public synthetic journal-entry benchmark after license verification, plus a project-owned seeded Indian-style dataset with planted anomalies and ground truth.

**Patent status:** This is a patent candidate, not a guaranteed patent. Existing prior art already covers general financial anomaly detection and AI-assisted audit/evidence tasks. The project will investigate a narrower technical mechanism and a formal claim strategy later.

**Next step:** Claude Code must run Phase 0 research and validation before implementation.

---

## Journal entry template
### YYYY-MM-DD HH:MM IST — [PHASE]
**What happened:**
**Why it matters:**
**Tests/checks:**
**Git commit:**
**Founder decision needed:**
**Credentials needed:**
**Next step:**
