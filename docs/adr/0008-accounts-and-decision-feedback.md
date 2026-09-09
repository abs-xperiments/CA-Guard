# ADR-0008 — Accounts, and telling a reviewer their decision landed

- **Date:** 2026-09-09
- **Status:** Accepted
- **Phase:** 8

## Two problems, one of them reported by the founder

**1. The audit trail could be signed by anybody.** The reviewer's name came from a text box on the page. Anyone could type anyone's name. That is not an audit trail; it is a suggestion, and a client is entitled to better.

**2. Pressing Accept appeared to do nothing.** The decision was recorded correctly and the interface said nothing at all. The row eventually vanished because the default filter hides reviewed items, which reads as a bug rather than a confirmation.

## Accounts

Local, in the same SQLite file as the decisions, so a firm still backs up one file.

| Decision | Reasoning |
|---|---|
| `hashlib.scrypt` for passwords | Memory-hard, and in the standard library. Argon2 is marginally better but is a compiled dependency; scrypt at 16 MB per hash is well within what a review would accept here. |
| Signed cookie, no server-side session table | Nothing to grow, nothing to clean up, and a cookie that cannot be edited by whoever holds it. |
| Signing key generated on first run | Nobody has to invent a secret to get started. Deleting the file logs everyone out, which is correct for a lost key. |
| Length over character classes | Character rules teach people to write `Password1!`. Ten characters minimum, with the reason explained rather than just enforced. |
| First account is the administrator | Somebody has to be able to get in. |
| **After that, signup needs an invite code** | A public URL with open signup is strangers uploading files. The code comes from `CAGUARD_INVITE_CODE` where set, and is otherwise generated once and printed. |
| Same message for a wrong password and an unknown address | So the endpoint cannot be used to discover which addresses have accounts. |

**The reviewer written into the trail comes from the session, never the request body.** `DecisionIn` no longer has a `reviewer` field at all, so sending one is rejected outright rather than silently used.

Every route touching a ledger requires a session, applied as a dependency rather than remembered per route — a route someone forgets to protect is the one that leaks. `/api/health` stays public so a container health check needs no credentials.

## Decision feedback

Research into how consumer applications handle reversible actions points consistently at one pattern: **act immediately, confirm briefly, and offer an undo**, rather than asking "are you sure?" beforehand. Friction should be proportional to how hard something is to reverse.

That fits this product unusually well. **Undo is not a deletion** — the trail is append-only, so undoing records a *further* decision that reopens the finding. The pleasant behaviour and the honest one turn out to be identical, and the fact that somebody changed their mind is preserved rather than erased.

Pressing a decision now does four things:

1. **The button itself changes** — to a tick reading "Done" — before anything moves.
2. **The row flashes once** and is held in the list for about a second, so a decision is not a row silently disappearing.
3. **A toast appears** saying what happened, what it means for the report, and offering Undo for six seconds.
4. **The queue advances** to the next unreviewed finding, because a reviewer working a list wants the next item.

Rejection keeps its friction: it still needs a typed reason, and it is deliberately not a bare keystroke, because it is the judgement someone will question later.

## Other adaptations from the same research

- **Skeletons rather than spinners** while a queue loads. A skeleton says what is coming and how much of it, and the page does not jump when content lands.
- **Progress always visible.** The header counters are derived from the findings on screen, so the bar actually moves.
- **Empty states carry an instruction**, and the "everything reviewed" state offers the report rather than just saying the list is empty.
- **Errors say what did *not* happen** — "Nothing was saved" — because after a failed action the first question is whether it half-worked.
- **`prefers-reduced-motion` disables every animation.** Motion is confirmation here, not decoration, and the confirmation still works without it.

## Consequences

- Anyone upgrading an existing installation creates an account on first launch; the existing decisions and their recorded names are untouched.
- A deployment must set `CAGUARD_INVITE_CODE`, or nobody but the first user can sign up.
- The `reviewer` field is gone from the decision API. Any caller sending it now gets a 422.
