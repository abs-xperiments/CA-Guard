# Repository Engineering Standards

## Structure principle
Keep frontend, backend, analytics, data, and evaluation concerns clearly separated. Do not scatter business logic across UI components.

## Rules
- Type-safe interfaces at boundaries.
- Validate external input at the boundary.
- Pure detection/scoring logic wherever possible.
- Small modules and cohesive services.
- No hidden global state.
- No hard-coded secrets.
- No magic constants without a named configuration.
- Reproducible random seeds in evaluation.
- Clear error messages.
- Tests close to business logic.
- One source of truth for schemas.

## Git
Use Conventional Commits:
- feat:
- fix:
- test:
- docs:
- refactor:
- chore:
- perf:
- security:

Never commit broken test suites knowingly.

## Branches
Use a small number of meaningful branches. For a student project, short-lived phase branches or direct commits to main are acceptable; do not create branch sprawl.

## Cleanup
After each phase:
- remove temporary scripts/files;
- remove dead code;
- remove unused dependencies;
- ensure `.env` and secrets are ignored;
- ensure generated datasets are not accidentally committed;
- run git status and inspect untracked files.
