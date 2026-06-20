<!--
clip_factory PR template. Delete any section that doesn't apply.
Code PRs (clipper/*.py, publish/*.py) ship via the ship-change skill.
Docs/config-only PRs: keep What/How, delete the review-gate + rights sections.
-->

## What
<!-- One or two sentences: what this change does and why. -->

## How
<!-- Key implementation points. Note any deviation from the plan/spec and why. -->

## Tests
<!-- Paste the pass line from: python3 -m pytest tests/ -q
     (The clipper-test hook also runs this automatically on clipper/**.py edits.) -->

```
```

## Review gate
<!-- Required for clipper/*.py and publish/*.py. Delete for docs/config-only PRs.
     Adversarial review (Codex and/or a code-reviewer agent) — gate: 0 Critical + 0 Important. -->
- [ ] Adversarial review done — 0 Critical, 0 Important

## Rights / publishing
<!-- Only if this touches publishing (publish/**). Delete otherwise. -->
- [ ] Source(s) listed in `SOURCES.md` with a rights basis
- [ ] Live smoke status noted (uploads default to private; confirm in YouTube Studio)
