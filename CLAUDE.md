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
