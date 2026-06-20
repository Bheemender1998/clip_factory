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
