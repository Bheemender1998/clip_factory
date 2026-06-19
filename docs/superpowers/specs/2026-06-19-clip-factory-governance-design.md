# clip_factory — governance & operational scaffolding design

**Date:** 2026-06-19
**Status:** Approved (brainstorm complete)

## Purpose

The clip_factory MVP shipped (clip generation, on `main`). This adds the
operational **governance scaffolding** — the structure, rules, enforcement hooks,
operational skills, and decision records — modeled on The Untold Game (TUG)'s
`engine/` governance, adapted to clip_factory's smaller, single-venv surface. The
goal: make the repo self-documenting and safe to operate/extend (especially as it
grows toward Stage 2 auto-posting), exactly the way TUG is.

No pipeline behavior changes. This is docs + hooks + skills + decision records.

## Components (4)

### 1. `CLAUDE.md` — the governance core

Project instructions, loaded every session. Sections:

- **Header** — one-line purpose; architecture modeled on TUG (`clipper/` engine,
  preview-gated build, future publish/learning loops).
- **Layout table** — each `clipper/*.py` stage + its role + status; `docs/`,
  `tests/`, `.claude/`.
- **Conventions:**
  - `python3`, never `python`.
  - All imports absolute `clipper.*`; run via `python3 -m clipper.run_clip`.
  - **Single venv** (`.venv`) — call out explicitly that, unlike TUG's load-bearing
    two-venv split, clip_factory uses one venv (faster-whisper + ffmpeg + anthropic
    coexist).
  - **System ffmpeg must have libass + libfreetype** (caption/text burn); core
    Homebrew ffmpeg lacks them — use the homebrew-ffmpeg tap build. `CLIP_FFMPEG`
    overrides the binary.
  - `ANTHROPIC_API_KEY` reused from `.env` (gitignored); never hardcode/commit it.
  - Per-call API cost logged to `logs/api-cost.jsonl`.
  - Docs/CLAUDE.md changes must not require a re-render to validate.
- **Hard rules:**
  - **NEVER push/work on `main`.** Branch (`feat/<slug>`) → PR → merge. The
    `push-guard` hook blocks a direct push to main.
  - **ALWAYS `python3 -m pytest tests/ -q` after editing `clipper/**.py`.** The
    `clipper-test` PostToolUse hook runs it automatically and wakes you on failure.
  - **Integrity / rights gate** — only clip source content you are authorized to
    use. Authorized sources live in `SOURCES.md` (the allowlist). Never publish a
    clip from an unlisted source without confirming rights. This is clip_factory's
    analog of TUG's fact-gate; it becomes enforced at Stage 2 (posting).
  - **Smallest sufficient change** — no speculative abstraction/config.
- **Gate discipline (the flow):**
  - Stage 1 = **clip generation — LIVE**.
  - Stage 2 = auto-post to TikTok / IG Reels / YouTube Shorts (planned).
  - Stage 3 = earnings/virality tracking vs predicted (planned).
  - Do **not** build Stage 2/3 speculatively — prove each stage's value first.
- **PR + review workflow** — `clipper/*.py` changes ship via the `ship-change`
  skill (branch → pytest → adversarial review → PR with review note → squash/merge).
  Docs/config-only PRs go plain (no review trailer).

### 2. Enforcement hooks (`.claude/hooks/` + `.claude/settings.json`)

- **`.claude/hooks/clipper-test.sh`** — PostToolUse on `Edit`/`Write`/`MultiEdit`
  whose file path is under `clipper/` and ends `.py`. Runs `python3 -m pytest
  tests/ -q` from the repo root; on failure emits a blocking/wake message. (Uses the
  same `python3` main env; no venv activation required for unit tests since
  integration deps are import-lazy.)
- **`.claude/hooks/push-guard.sh`** — PreToolUse on `Bash`. Blocks a command that
  pushes to `main` (`git push` targeting main while on/declaring main). Mirrors
  TUG's guard; makes the rule repo-local and explicit.
- **`.claude/settings.json`** — wires both hooks (PreToolUse → push-guard,
  PostToolUse → clipper-test), matching TUG's structure.

Both scripts are bash, executable, and self-contained (no external deps).

### 3. Operational skills (`.claude/skills/`)

Each is a `SKILL.md` (name + description + steps) wrapping an entrypoint, invocable
by name. Right-sized to the current surface:

| Skill | Wraps / does |
|-------|--------------|
| `make-clips` | `python3 -m clipper.run_clip <url> --n <N>` — batch generate; reminds to check `SOURCES.md` rights first. |
| `preview-clip` | `python3 -m clipper.run_clip <url> --preview` — render one clip for eyeball before a batch. |
| `cost-report` | summarize `logs/api-cost.jsonl` (spend by stage/run) via a new tiny `clipper/cost_report.py` (mirrors TUG's `run_cost_report`). |
| `ship-change` | the release rail for `clipper/*.py`: branch → `pytest tests/ -q` → adversarial review → PR. |
| `handoff` | append a session-wrap entry to `HANDOFF.md` (created if absent). |

### 4. ADRs + roadmap (`docs/`)

- **`docs/adr/`** — seed decision records (TUG-style, short):
  - `0001-clip-generation-only-scope.md` — Stage-1-only MVP, posting/discovery deferred.
  - `0002-yt-dlp-over-youtube-dl.md` — maintained fork; original is unmaintained.
  - `0003-blurred-pad-reframe.md` — chose blurred-pad over center-crop at the preview gate.
  - `0004-ffmpeg-libass-requirement.md` — captions need libass/libfreetype; tap build; `CLIP_FFMPEG`.
  - `0005-clip-length-shorts-cap.md` — ~40s target, 20–55s cap (under YouTube's 60s Shorts threshold).
- **`docs/execution-plan.md`** — the staged roadmap (Stage 1 LIVE → 2 → 3) with
  what proves each gate.
- **`README.md`** — quickstart (venv, `.env`, the two run commands) + the
  ffmpeg-libass setup note + a pointer to `CLAUDE.md`/`docs/`.

## New code (minimal)

- `clipper/cost_report.py` — reads `logs/api-cost.jsonl`, prints spend grouped by
  `stage` and totals; optional `--run`-style filter later. Unit-tested with a
  fixture ledger (deterministic). This is the only executable code added.
- `SOURCES.md` — the authorized-source allowlist (initially a documented template:
  channels/creators/campaigns you have rights to clip).

## Testing

- `cost_report` gets unit tests (fixture JSONL → expected grouped totals), following
  the existing TDD pattern.
- Hooks are validated by a smoke check (touch a `clipper/*.py`, confirm the test
  hook fires; attempt a guarded push string, confirm the guard blocks) — manual,
  documented in the plan, not a unit test.
- Skills/ADRs/docs are prose — reviewed for accuracy, not unit-tested.

## Out of scope (YAGNI)

- Actual Stage 2 posting / Stage 3 tracking code.
- Enforcing `SOURCES.md` programmatically in the pipeline (documented rule now;
  enforcement lands with Stage 2 posting, where it bites).
- Railway/cron deploy scaffolding (clip_factory render is local; no cron yet).

## Conventions carried from the MVP

`python3`; absolute `clipper.*` imports; single venv; `pytest tests/ -q` is the
contract; smallest sufficient change. Built per the same brainstorm→spec→plan→
subagent-driven-TDD rail as the MVP.
