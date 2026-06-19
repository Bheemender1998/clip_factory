# clip_factory Governance Scaffolding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add TUG-style operational governance to clip_factory — `CLAUDE.md`, enforcement hooks, operational skills, ADRs, a roadmap, a README, and a `SOURCES.md` rights allowlist — plus one small `cost_report.py` module so the cost-report skill has something to wrap.

**Architecture:** Pure scaffolding — docs + bash hooks + `SKILL.md` playbooks + decision records. The only executable code is `clipper/cost_report.py` (reads the existing `logs/api-cost.jsonl` ledger), which is built TDD-first. No pipeline behavior changes.

**Tech Stack:** Markdown, bash (hooks), JSON (`.claude/settings.json`), Python 3 (`cost_report.py`), pytest.

## Global Constraints

- **`python3`, never `python`.** Absolute imports `clipper.*`.
- **Single venv** (`.venv`) — clip_factory has no two-venv split.
- **System ffmpeg must have libass + libfreetype**; `CLIP_FFMPEG` overrides the binary.
- **NEVER push/work on `main`** — branch → PR → merge.
- **ALWAYS `python3 -m pytest tests/ -q` after editing `clipper/**.py`.**
- **Rights gate** — only clip sources listed in `SOURCES.md`; documented now, enforced at Stage 2.
- **Smallest sufficient change** — no speculative abstraction.
- The cost ledger path is `logs/api-cost.jsonl` (under `config.ROOT`); records have keys `ts, stage, model, input_tokens, output_tokens, cost_usd`.
- All new docs/skills must NOT require a render to validate.

---

### Task 1: `cost_report.py` + cost-report skill

**Files:**
- Create: `clipper/cost_report.py`
- Create: `tests/test_cost_report.py`
- Create: `.claude/skills/cost-report/SKILL.md`

**Interfaces:**
- Consumes: `config.ROOT`.
- Produces: `cost_report.load_records(ledger=LEDGER) -> list[dict]`; `cost_report.summarize(records) -> dict` (`{"by_stage": {stage: {"calls","input_tokens","output_tokens","cost_usd"}}, "total_cost": float}`); `cost_report.format_report(summary) -> str`; `cost_report.main(argv=None) -> int`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cost_report.py
import json

from clipper import cost_report


def _write(ledger, rows):
    ledger.write_text("\n".join(json.dumps(r) for r in rows) + "\n")


def test_load_records_skips_blank_lines(tmp_path):
    led = tmp_path / "api-cost.jsonl"
    led.write_text('{"stage":"select","cost_usd":1.0}\n\n')
    recs = cost_report.load_records(led)
    assert len(recs) == 1 and recs[0]["stage"] == "select"


def test_load_records_missing_file_is_empty(tmp_path):
    assert cost_report.load_records(tmp_path / "nope.jsonl") == []


def test_summarize_groups_by_stage_and_totals():
    recs = [
        {"stage": "select", "input_tokens": 10, "output_tokens": 5, "cost_usd": 1.0},
        {"stage": "select", "input_tokens": 20, "output_tokens": 5, "cost_usd": 2.0},
        {"stage": "metadata", "input_tokens": 4, "output_tokens": 2, "cost_usd": 0.5},
    ]
    s = cost_report.summarize(recs)
    assert s["total_cost"] == 3.5
    assert s["by_stage"]["select"]["calls"] == 2
    assert s["by_stage"]["select"]["input_tokens"] == 30
    assert s["by_stage"]["metadata"]["cost_usd"] == 0.5


def test_format_report_has_total_line():
    out = cost_report.format_report(cost_report.summarize(
        [{"stage": "select", "input_tokens": 1, "output_tokens": 1, "cost_usd": 2.0}]))
    assert "select" in out
    assert "TOTAL" in out
    assert "2.0000" in out
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_cost_report.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'clipper.cost_report'`

- [ ] **Step 3: Write `clipper/cost_report.py`**

```python
import json
import sys
from collections import defaultdict
from pathlib import Path

from clipper import config

LEDGER = config.ROOT / "logs" / "api-cost.jsonl"


def load_records(ledger=LEDGER) -> list:
    ledger = Path(ledger)
    if not ledger.exists():
        return []
    out = []
    for line in ledger.read_text().splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def summarize(records) -> dict:
    by_stage = defaultdict(
        lambda: {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    )
    total = 0.0
    for r in records:
        s = by_stage[r.get("stage", "?")]
        s["calls"] += 1
        s["input_tokens"] += r.get("input_tokens", 0)
        s["output_tokens"] += r.get("output_tokens", 0)
        s["cost_usd"] += r.get("cost_usd", 0.0)
        total += r.get("cost_usd", 0.0)
    return {"by_stage": dict(by_stage), "total_cost": round(total, 6)}


def format_report(summary) -> str:
    lines = [f"{'stage':<12} {'calls':>5} {'in_tok':>9} {'out_tok':>9} {'cost_usd':>11}"]
    for stage, s in sorted(summary["by_stage"].items()):
        lines.append(
            f"{stage:<12} {s['calls']:>5} {s['input_tokens']:>9} "
            f"{s['output_tokens']:>9} {s['cost_usd']:>11.4f}"
        )
    lines.append(f"{'TOTAL':<12} {'':>5} {'':>9} {'':>9} {summary['total_cost']:>11.4f}")
    return "\n".join(lines)


def main(argv=None) -> int:
    print(format_report(summarize(load_records())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_cost_report.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Write the cost-report skill**

```markdown
<!-- .claude/skills/cost-report/SKILL.md -->
---
name: cost-report
description: Summarize clip_factory API spend from logs/api-cost.jsonl by stage. Use when the user says "cost report", "how much did clipping cost", "check API spend", or "/cost-report".
---

# cost-report

Summarize per-call API spend (select + metadata LLM calls) from the JSONL ledger.

## Steps

1. Run the report:
   ```bash
   python3 -m clipper.cost_report
   ```
2. Read the table: spend grouped by `stage` (select / metadata), with token counts and a TOTAL line.
3. If `logs/api-cost.jsonl` is missing, the report is empty — that means no LLM calls have run yet.
4. Relay the TOTAL and the per-stage breakdown to the user; flag if a single run looks unusually expensive.
```

- [ ] **Step 6: Run the full suite**

Run: `python3 -m pytest tests/ -q`
Expected: PASS (36 passed — 32 prior + 4 new)

- [ ] **Step 7: Commit**

```bash
git add clipper/cost_report.py tests/test_cost_report.py .claude/skills/cost-report/SKILL.md
git commit -m "feat(cost-report): ledger summary command + skill"
```

---

### Task 2: Enforcement hooks

**Files:**
- Create: `.claude/hooks/clipper-test.sh`
- Create: `.claude/hooks/push-guard.sh`
- Create: `.claude/settings.json`

**Interfaces:**
- Produces: a PostToolUse hook that runs pytest after `clipper/**.py` edits, and a PreToolUse hook that blocks direct pushes to `main`.

- [ ] **Step 1: Write `.claude/hooks/clipper-test.sh`**

```bash
#!/usr/bin/env bash
# PostToolUse: after an Edit/Write/MultiEdit to clipper/**.py, run the test suite.
# Reads the hook payload (JSON) on stdin; only fires for clipper/*.py paths.
set -euo pipefail
payload="$(cat)"
file="$(printf '%s' "$payload" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))' 2>/dev/null || true)"
case "$file" in
  *clipper/*.py)
    cd "$(git rev-parse --show-toplevel)"
    if ! python3 -m pytest tests/ -q >/tmp/clipper-pytest.log 2>&1; then
      echo "clipper tests FAILED after editing $file — see /tmp/clipper-pytest.log" >&2
      tail -20 /tmp/clipper-pytest.log >&2
      exit 2
    fi
    ;;
esac
exit 0
```

- [ ] **Step 2: Write `.claude/hooks/push-guard.sh`**

```bash
#!/usr/bin/env bash
# PreToolUse(Bash): block a command that pushes to main directly.
set -euo pipefail
payload="$(cat)"
cmd="$(printf '%s' "$payload" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' 2>/dev/null || true)"
if printf '%s' "$cmd" | grep -Eq 'git[[:space:]]+push'; then
  if printf '%s' "$cmd" | grep -Eq '(^|[[:space:]])main([[:space:]]|$)' \
     || [ "$(git rev-parse --abbrev-ref HEAD 2>/dev/null)" = "main" ]; then
    echo "On main: never push main directly. Branch (feat/...), open a PR, then merge." >&2
    exit 2
  fi
fi
exit 0
```

- [ ] **Step 3: Make the hooks executable**

Run: `chmod +x .claude/hooks/clipper-test.sh .claude/hooks/push-guard.sh`
Expected: no output (success)

- [ ] **Step 4: Write `.claude/settings.json`**

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/push-guard.sh" }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [
          { "type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/clipper-test.sh" }
        ]
      }
    ]
  }
}
```

- [ ] **Step 5: Smoke-check the push guard**

Run:
```bash
echo '{"tool_input":{"command":"git push origin main"}}' | .claude/hooks/push-guard.sh; echo "exit=$?"
echo '{"tool_input":{"command":"git push origin feat/x"}}' | .claude/hooks/push-guard.sh; echo "exit=$?"
```
Expected: first prints the guard message and `exit=2`; second prints `exit=0`.

- [ ] **Step 6: Smoke-check the test hook routing (non-clipper path is a no-op)**

Run:
```bash
echo '{"tool_input":{"file_path":"README.md"}}' | .claude/hooks/clipper-test.sh; echo "exit=$?"
```
Expected: `exit=0` (no pytest run — README isn't under clipper/).

- [ ] **Step 7: Commit**

```bash
git add .claude/hooks/clipper-test.sh .claude/hooks/push-guard.sh .claude/settings.json
git commit -m "feat(hooks): pytest-on-clipper-edit + push-to-main guard"
```

---

### Task 3: `CLAUDE.md` — the governance core

**Files:**
- Create: `CLAUDE.md`

- [ ] **Step 1: Write `CLAUDE.md`**

```markdown
# clip_factory — project instructions

High-volume short-form **clip generator** for clip-to-earn work (Content Rewards /
Whop clipping campaigns). Turns a long YouTube video into ready-to-post 9:16 clips
with karaoke captions, a hook headline, and LLM-written social metadata. Modeled on
The Untold Game (TUG)'s `engine/` governance, adapted to a smaller single-venv tool.

## Layout

| Path | Role | Status |
|------|------|--------|
| `clipper/fetch.py` | yt-dlp download (URL or `ytsearch:`) | LIVE |
| `clipper/transcribe.py` | faster-whisper word-timed transcript | LIVE |
| `clipper/select.py` | LLM picks top-N viral moments, boundary-snapped | LIVE |
| `clipper/render.py` + `captions.py` | ffmpeg blurred-pad 9:16 + ASS karaoke + hook | LIVE |
| `clipper/metadata.py` | LLM title/caption/hashtags | LIVE |
| `clipper/cost_log.py` / `cost_report.py` | per-call cost ledger + summary | LIVE |
| `clipper/run_clip.py` | CLI: `--preview` (one clip) / `--n` (batch) | LIVE |
| `publish/` | Stage 2 auto-post (TikTok/IG/YT) | planned |
| `outcomes/` | Stage 3 earnings/virality tracking | planned |
| `docs/adr/`, `docs/execution-plan.md` | decisions + roadmap | LIVE |

## Conventions

- **`python3`, not `python`** — this machine has no `python` binary.
- **All imports absolute `clipper.*`** — run via `python3 -m clipper.run_clip`.
- **Single venv** (`.venv`) — unlike TUG's load-bearing two-venv split, faster-whisper
  + ffmpeg + anthropic coexist here. One venv.
- **System ffmpeg must have libass + libfreetype** (caption/text burn). Core Homebrew
  ffmpeg lacks them — use the `homebrew-ffmpeg/ffmpeg` tap build. `CLIP_FFMPEG`
  overrides the binary.
- **`ANTHROPIC_API_KEY` is reused from `.env`** (gitignored). Never hardcode or commit it.
- **Web search / LLM cost is logged** to `logs/api-cost.jsonl`; summarize with
  `python3 -m clipper.cost_report`.
- Docs/CLAUDE.md changes must not require a render to validate.

## Entrypoints

```bash
python3 -m clipper.run_clip "<url>" --preview     # render the single best clip (eyeball gate)
python3 -m clipper.run_clip "<url>" --n 6         # batch: top-N clips + meta.json each
python3 -m clipper.cost_report                    # API spend by stage
```

## Skills (`.claude/skills/`)

| Skill | Wraps |
|-------|-------|
| `make-clips` | `run_clip --n` — batch generate |
| `preview-clip` | `run_clip --preview` — one-clip gate |
| `cost-report` | `cost_report` — API spend summary |
| `ship-change` | the release rail for `clipper/*.py` |
| `handoff` | append a session wrap to `HANDOFF.md` |

## Gate discipline

- Stage 1 = **clip generation — LIVE**.
- Stage 2 = auto-post to TikTok / IG Reels / YouTube Shorts — **planned**.
- Stage 3 = earnings / virality tracking vs predicted — **planned**.

Do **not** build Stage 2/3 speculatively. Prove each stage's value before expanding
surface.

## Hard rules

- **NEVER push `main` directly / NEVER work on `main`.** Branch (`feat/<slug>`), PR,
  merge — the `push-guard` hook blocks a direct push while on/at main.
- **ALWAYS `python3 -m pytest tests/ -q` after editing `clipper/**.py`.** The
  `clipper-test` PostToolUse hook runs it automatically and fails loudly.
- **Rights / integrity gate** — only clip source content you are authorized to use.
  Authorized sources live in `SOURCES.md`. Never publish a clip from an unlisted
  source without confirming rights. This is clip_factory's analog of TUG's fact-gate;
  it becomes programmatically enforced at Stage 2 (posting).
- **Two run modes** — `--preview` is the human eyeball gate; only run a `--n` batch
  after the look is approved for that source.
- **Smallest sufficient change** — no speculative abstraction/config; touch only what
  the stated success criteria require.

## PR + review workflow

`clipper/*.py` changes ship via the **`ship-change`** skill:

```
git checkout -b feat/<slug>
python3 -m pytest tests/ -q          # contract (the hook runs it too)
# adversarial review (Codex and/or a code-reviewer agent); gate: 0 Critical + 0 Important
gh pr create --base main             # push via gh (a guard blocks `git push` from the shell)
gh pr merge --merge --delete-branch
```

**Docs/config-only PRs:** plain `gh pr create --base main` (no review trailer).

**Render is local** (the M5 — captions need the font-enabled ffmpeg). Never run a
render in a hook or in CI.
```

- [ ] **Step 2: Verify it renders as valid markdown (no broken fences)**

Run: `grep -c '^```' CLAUDE.md`
Expected: an even number (all code fences balanced).

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(governance): CLAUDE.md — conventions, hard rules, gate discipline"
```

---

### Task 4: Operational skills

**Files:**
- Create: `.claude/skills/make-clips/SKILL.md`
- Create: `.claude/skills/preview-clip/SKILL.md`
- Create: `.claude/skills/ship-change/SKILL.md`
- Create: `.claude/skills/handoff/SKILL.md`

- [ ] **Step 1: Write `.claude/skills/make-clips/SKILL.md`**

```markdown
---
name: make-clips
description: Batch-generate ready-to-post 9:16 clips from a YouTube video. Use when the user says "make clips", "clip this video", "run the batch", or "/make-clips".
---

# make-clips

Generate the top-N clips from a source video, each with karaoke captions, a hook, and meta.json.

## Steps

1. **Rights check (hard gate):** confirm the source is authorized — its channel/creator/campaign must be listed in `SOURCES.md`. If it is not, stop and ask the user to confirm rights before clipping.
2. Activate the venv and run the batch (default N=6; pass the user's count):
   ```bash
   . .venv/bin/activate
   python3 -m clipper.run_clip "<url>" --n <N>
   ```
3. Output lands in `output/<video_id>/clip_NN/{clip_NN.mp4, meta.json}`. Relay the clip count and paths.
4. If clips were skipped (`[skip] clip N failed: ...`), report which and why.
5. Suggest `/preview-clip` first if the user hasn't validated the look for this source.
```

- [ ] **Step 2: Write `.claude/skills/preview-clip/SKILL.md`**

```markdown
---
name: preview-clip
description: Render ONE clip from a video to eyeball the crop, captions, and hook before a full batch. Use when the user says "preview", "show me one clip", or "/preview-clip".
---

# preview-clip

Render the single best moment so the user can approve the look before committing to a batch.

## Steps

1. **Rights check:** confirm the source is in `SOURCES.md` (see make-clips).
2. Run the preview:
   ```bash
   . .venv/bin/activate
   python3 -m clipper.run_clip "<url>" --preview
   ```
3. The clip lands at `output/<video_id>/clip_01/clip_01.mp4`. Open it (`open <path>`) or extract a frame with ffmpeg for the user to inspect crop / caption style / hook.
4. If the look is wrong, the fix is in the render stage (`render.py` / `captions.py`) — adjust there, never downstream.
```

- [ ] **Step 3: Write `.claude/skills/ship-change/SKILL.md`**

```markdown
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
```

- [ ] **Step 4: Write `.claude/skills/handoff/SKILL.md`**

```markdown
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
```

- [ ] **Step 5: Verify all four skills have valid frontmatter**

Run: `for f in make-clips preview-clip ship-change handoff; do head -1 ".claude/skills/$f/SKILL.md"; done`
Expected: each prints `---` (frontmatter opens correctly).

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/make-clips .claude/skills/preview-clip .claude/skills/ship-change .claude/skills/handoff
git commit -m "feat(skills): make-clips, preview-clip, ship-change, handoff"
```

---

### Task 5: ADRs, roadmap, README, SOURCES

**Files:**
- Create: `docs/adr/0001-clip-generation-only-scope.md`
- Create: `docs/adr/0002-yt-dlp-over-youtube-dl.md`
- Create: `docs/adr/0003-blurred-pad-reframe.md`
- Create: `docs/adr/0004-ffmpeg-libass-requirement.md`
- Create: `docs/adr/0005-clip-length-shorts-cap.md`
- Create: `docs/execution-plan.md`
- Create: `README.md`
- Create: `SOURCES.md`

- [ ] **Step 1: Write the 5 ADRs**

`docs/adr/0001-clip-generation-only-scope.md`:
```markdown
# 0001 — Clip generation only (Stage 1) for the MVP

**Status:** Accepted (2026-06-19)

## Context
clip_factory targets clip-to-earn work, which spans discovery → clipping → posting →
earnings. Building all of it up front risks heavy surface before any value is proven.

## Decision
The MVP does **clip generation only**: URL in → 9:16 clips + metadata out. No campaign
discovery, no auto-posting, no earnings tracking. The human posts manually.

## Consequences
Fast to prove. Stages 2 (posting) and 3 (tracking) are gated — built only after Stage 1
value is real. See `docs/execution-plan.md`.
```

`docs/adr/0002-yt-dlp-over-youtube-dl.md`:
```markdown
# 0002 — yt-dlp over the original youtube-dl

**Status:** Accepted (2026-06-19)

## Context
The user pointed at `ytdl-org/youtube-dl` for downloads. It is effectively unmaintained
and frequently breaks on current YouTube.

## Decision
Use **yt-dlp** (the maintained fork): same CLI shape, the `ytsearch:` query syntax, and
it actually works on today's YouTube.

## Consequences
Reliable downloads; `fetch.py` wraps yt-dlp. No functional reason to use the original.
```

`docs/adr/0003-blurred-pad-reframe.md`:
```markdown
# 0003 — Blurred-pad reframe instead of center-crop

**Status:** Accepted (2026-06-19, at the preview gate)

## Context
The spec proposed center-cropping 16:9 → 9:16. The first preview showed center-crop
keeps the middle column — fine for single-speaker close-ups, but it cut both speakers
out of wide two-shots.

## Decision
Render **blurred-pad**: the full 16:9 frame centered over a blurred, zoomed fill that
covers the 9:16 canvas. Nothing is cropped out. The hook headline is word-wrapped to fit.

## Consequences
Robust to any framing; the common "podcast clip" look. Slightly less full-bleed than a
crop. Implemented in `render.build_vf`.
```

`docs/adr/0004-ffmpeg-libass-requirement.md`:
```markdown
# 0004 — ffmpeg must have libass + libfreetype

**Status:** Accepted (2026-06-19)

## Context
Captions burn via the `ass` filter (libass) and the hook via `drawtext` (libfreetype).
The macOS core Homebrew ffmpeg ships **without** these libraries — no `ass`/`drawtext`
filters — so the render fails at the filtergraph.

## Decision
Require a font-enabled ffmpeg: the `homebrew-ffmpeg/ffmpeg` tap build (8.1.2+).
`config.FFMPEG` (env `CLIP_FFMPEG`) overrides the binary so a font-enabled build can be
pointed at without replacing the system one (note: the tap build can't coexist with core
under the same keg name, so the system ffmpeg was upgraded to the tap build).

## Consequences
A documented setup prerequisite (see README). TUG never hit this because Remotion bundles
its own ffmpeg.
```

`docs/adr/0005-clip-length-shorts-cap.md`:
```markdown
# 0005 — Clip length: ~40s target, 20–55s cap

**Status:** Accepted (2026-06-19)

## Context
Default clip length ran long (50–85s). YouTube classifies only videos ≤ 60s as Shorts,
and short-form performs best around 30–45s.

## Decision
Target **~40s**, hard-cap **20–55s** (`CLIP_MIN_SEC` / `CLIP_TARGET_SEC` / `CLIP_MAX_SEC`).
The selector prompt asks for ~40s; `snap_bounds` enforces the bounds. Every clip stays
under the 60s Shorts threshold.

## Consequences
Shorts-eligible clips by construction. Configurable via env if a platform wants longer.
```

- [ ] **Step 2: Write `docs/execution-plan.md`**

```markdown
# clip_factory — execution plan

A staged roadmap. Each stage is gated: prove its value before building the next.

## Stage 1 — Clip generation (LIVE)
URL → top-N 9:16 clips + `meta.json`. Pipeline: fetch → transcribe → select → render →
metadata. CLI, preview-gated. **Done.**

## Stage 2 — Auto-post (planned)
Publish clips to TikTok / IG Reels / YouTube Shorts on a schedule, across accounts.
Gate to start: a real backlog of approved Stage-1 clips worth posting, and the
`SOURCES.md` rights allowlist enforced programmatically before any upload.

## Stage 3 — Earnings / virality tracking (planned)
Track posted-clip performance (views, earnings per campaign) vs the selector's predicted
virality; feed it back to improve moment selection. Gate: real posted clips with
measurable outcomes.

## Standing principles
- Smallest sufficient change; no speculative stage work.
- Local render (font-enabled ffmpeg); never render in a hook or CI.
- Rights gate first: only clip authorized sources (`SOURCES.md`).
```

- [ ] **Step 3: Write `README.md`**

```markdown
# clip_factory

Turn a long YouTube video into ready-to-post **9:16 short clips** — karaoke captions, a
hook headline, and LLM-written title/caption/hashtags per clip. For clip-to-earn work
(Content Rewards / Whop).

## Setup

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
echo "ANTHROPIC_API_KEY=sk-..." > .env        # gitignored
```

**ffmpeg must have libass + libfreetype** (caption/text burn). The core Homebrew ffmpeg
does NOT — install the font-enabled tap build:

```bash
brew uninstall ffmpeg
brew install homebrew-ffmpeg/ffmpeg/ffmpeg
# or set CLIP_FFMPEG to a font-enabled ffmpeg binary
```

## Run

```bash
python3 -m clipper.run_clip "<youtube-url>" --preview   # one clip, to eyeball the look
python3 -m clipper.run_clip "<youtube-url>" --n 6        # batch top-6
python3 -m clipper.cost_report                           # API spend by stage
```

Output: `output/<video_id>/clip_NN/{clip_NN.mp4, meta.json}`.

## Docs
- `CLAUDE.md` — conventions, hard rules, gate discipline.
- `docs/execution-plan.md` — staged roadmap.
- `docs/adr/` — decision records.
- `SOURCES.md` — authorized-source allowlist (rights gate).
```

- [ ] **Step 4: Write `SOURCES.md`**

```markdown
# Authorized sources (rights gate)

Only clip content you have the right to use. List authorized channels, creators, and
clip-to-earn campaigns below. The make-clips / preview-clip workflow checks a source
against this list before clipping; Stage 2 (posting) will enforce it programmatically.

## Format
- **<name>** — <channel/URL or campaign id> — <rights basis> — <added date>

## Authorized
_(none yet — add entries as campaigns are accepted)_

## Notes
- A source not listed here is NOT authorized. Confirm rights with the user before clipping it.
- Content Rewards / Whop campaigns define their own allowed source material — copy those terms here.
```

- [ ] **Step 5: Verify markdown fences are balanced across the new docs**

Run: `for f in docs/execution-plan.md README.md SOURCES.md docs/adr/000*.md; do echo "$f: $(grep -c '^```' "$f")"; done`
Expected: every count is even.

- [ ] **Step 6: Commit**

```bash
git add docs/adr docs/execution-plan.md README.md SOURCES.md
git commit -m "docs(governance): ADRs, execution plan, README, SOURCES allowlist"
```

---

## Notes for the executor

- The `clipper-test` PostToolUse hook only exists after Task 2. If it ever blocks a
  later docs-only edit, that's a bug in the path filter — it must no-op on non-`clipper/*.py`
  files (verified in Task 2 Step 6).
- All tasks except Task 1 are prose/config; their "test" is the balance/frontmatter check
  shown. Task 1 is the only one with unit tests.
- Final suite after the whole plan: `python3 -m pytest tests/ -q` → 36 passed.
