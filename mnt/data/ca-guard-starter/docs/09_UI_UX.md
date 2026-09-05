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
