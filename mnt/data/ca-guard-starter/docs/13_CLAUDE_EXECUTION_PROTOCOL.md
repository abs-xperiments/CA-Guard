# Claude Execution Protocol

Claude Code is the primary autonomous builder. The project deliberately uses persistent project instructions, phase plans, tests, and journal entries so multiple sessions remain coherent.

## Session protocol
At session start:
1. Read CLAUDE.md and relevant docs.
2. Inspect git status/history.
3. Read journal.md.
4. Identify current phase.
5. Continue only from the documented acceptance criteria.

## Research protocol
For any material external dependency, Claude must:
- search current official documentation first;
- verify license/cost/compatibility;
- prefer primary sources;
- record the decision in an ADR or the appropriate doc.

## Implementation protocol
Before implementation:
- define acceptance criteria;
- identify test cases;
- implement the smallest coherent increment;
- run tests;
- fix all known failures;
- document result;
- commit.

## Tooling protocol
Claude may use web research, local scripts, package managers, and MCP where available. Do not add an MCP server or paid tool merely because it is available.

Claude Code supports CLAUDE.md, auto memory, hooks, and MCP. Use hooks only for deterministic guardrails that genuinely reduce risk, such as formatting or verification; do not build a complicated automation system inside the project.

Sources:
- https://code.claude.com/docs/en/memory
- https://code.claude.com/docs/en/hooks
- https://code.claude.com/docs/en/mcp
