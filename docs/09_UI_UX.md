# UI/UX Direction

## Design goal
A CA should understand the screen in seconds. The product should feel like a calm professional audit workspace, not a flashy AI toy.

## Main screens
1. Login / secure workspace entry
2. Review workspace list
3. New review / dataset upload
4. Data mapping and validation
5. Analysis progress
6. Findings dashboard
7. Finding detail + evidence drawer
8. Review decision panel
9. Report/export screen
10. Settings / privacy mode

## Visual priorities
- strong typography hierarchy;
- dense but readable transaction tables;
- obvious High/Medium/Low prioritization;
- evidence first, AI prose second;
- clear empty/loading/error states;
- accessible keyboard navigation;
- responsive layout for laptop-first use.

## Animation policy
Use subtle transitions for:
- page changes;
- filter state;
- finding expansion;
- progress/status;
- evidence drawer;
- success/decision confirmation.

Do not animate high-density tables excessively.

## Inspiration research
Use 21st.dev for dashboard, sidebar, table, sign-in, and interaction patterns. Prefer components that can be copied and owned locally. shadcn/ui is open-source and provides composable components.

Sources:
- 21st dashboard examples: https://21st.dev/community/components/s/dashboard
- shadcn/ui: https://ui.shadcn.com/docs

## Accessibility and layout (verified 2026-10-08 01:38 IST)

**Accessibility.** Automated WCAG 2.2 AA scans (axe-core) show **0 violations** on sign-up, home, the review queue, the open finding and the file preview. Fixed to get there:
- small-print grey raised to 4.5:1 contrast via the design tokens (`--color-ink-muted` #475569, `--color-ink-faint` #627084), on white, canvas and the selected-row background;
- an accessible name on the "back" link;
- a `main` landmark;
- keyboard-scrollable queue and dialog bodies;
- the drawer's voucher number as its level-2 heading.

**Widths.**

| Width | Behaviour |
|---|---|
| 1440 px | All seven queue columns; drawer beside the queue. |
| 1024 px, finding open | The queue drops date, evidence and status by **container query** (its own width, not the window's). No horizontal overflow. |
| 768 px and below | The drawer covers the screen; Escape returns to the queue. |

Tables use a fixed layout, so long narrations and crore-sized amounts truncate instead of pushing the page sideways.

**First run and the demo.**
- A brand-new install opens straight on "Create your account".
- The upload area says what a usable export contains.
- **"Try it with a sample ledger"** opens a committed synthetic Tally-style day book (`scripts/make_sample_ledger.py`, seed 20251001: not a benchmark seed). It is read from a file, so the product never imports the generator (ADR-0003).

