---
name: handoff
description: Append a session-wrap entry to HANDOFF.md so the next agent can pick up. Use when the user says "wrap the session", "handoff", "/handoff", or signals end-of-session.
---

# handoff

Append a dated session summary to `HANDOFF.md` (create it if absent).

## Steps

1. Summarize this session: what shipped (commits/PRs), what's in flight, and the next obvious step.
2. Append to `HANDOFF.md` under a new `## Session — <date>` heading. Create the file with a `# clip_factory — handoff log` title if it does not exist.
3. Keep it short and factual — commits, decisions, open threads. Convert relative dates to absolute.
4. Do not commit unless the user asks; if you do, it is a docs-only change (plain commit, no review).
