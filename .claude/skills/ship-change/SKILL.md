---
name: ship-change
description: The release rail for any clipper/*.py change — feature branch, pytest, adversarial review, PR. Use when the user says "ship this", "open the PR", or is finishing clipper/*.py work. Do NOT use for docs-only changes (plain gh pr create).
---

# ship-change

Ship a `clipper/*.py` change safely.

## Steps

1. Branch off main:
   ```bash
   git checkout -b feat/<slug>
   ```
2. Run the contract (the PostToolUse hook also runs it):
   ```bash
   python3 -m pytest tests/ -q
   ```
3. Adversarial review — run a Codex pass and/or spawn a code-reviewer agent on the diff. Gate: **0 Critical + 0 Important** before proceeding.
4. Open the PR (push via `gh`; a shell guard blocks `git push` to main):
   ```bash
   gh pr create --base main --title "..." --body "..."
   ```
5. After approval, merge:
   ```bash
   gh pr merge --merge --delete-branch
   ```

Docs/config-only changes skip review — use a plain `gh pr create`.
