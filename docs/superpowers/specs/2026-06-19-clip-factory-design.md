# clip_factory — design

**Date:** 2026-06-19
**Status:** Approved (brainstorm complete, preview-gated build)

## One line

Paste a YouTube URL → get a folder of 5–8 ready-to-post 9:16 clips, each with
karaoke captions, a hook headline, and a written social caption/title/hashtags.

## Purpose & context

A standalone, high-volume short-form **clip generator** for clip-to-earn work
(e.g. Content Rewards / Whop clipping campaigns). It is modeled on the Untold
Game (TUG) `engine/` architecture but is an **independent repo** — no shared code,
just shared conventions and the reused `ANTHROPIC_API_KEY` from `.env`.

**Scope is clip generation only.** Out of scope (explicitly): campaign discovery,
auto-posting to social platforms, and view/earnings tracking. The human posts the
clips manually.

## Decisions (locked during brainstorm)

| Question | Decision |
|----------|----------|
| Core scope | Clip generation only — no posting, no campaign discovery |
| Source input | Long YouTube videos / podcasts (URL, 1–3 hr) |
| Moment selection | LLM picks the top N viral moments from the transcript (no review step) |
| Render style | Approach A — pure ffmpeg: 9:16 + ASS karaoke captions + hook headline |
| Reframe | **Blurred-pad** — full 16:9 frame centered over a blurred fill (chosen at the preview gate; center-crop cut speakers out of wide two-shots). Hook headline is word-wrapped to fit. |
| Clip length | Target ~40s, hard-capped 20–55s so every clip stays under YouTube's 60s Shorts threshold (`CLIP_MIN_SEC`/`CLIP_TARGET_SEC`/`CLIP_MAX_SEC`). |
| Per-clip output | MP4 + post metadata (LLM caption/title/hashtags) |
| Run model | CLI, auto top-N, default 6 clips (configurable), no approval queue |
| ffmpeg | System ffmpeg must have libass + libfreetype (caption/text burn). `CLIP_FFMPEG` overrides the binary; the macOS core Homebrew ffmpeg lacks these — use the homebrew-ffmpeg tap build. |
| Project home | Brand-new separate repo (`~/clip_factory`) |
| Downloader | **yt-dlp** (maintained fork; the original `youtube-dl` is unmaintained and breaks on current YouTube). Supports `ytsearch:"query"` for finding videos. |
| Transcription | Local `faster-whisper` — free, runs on the M5, gives word-level timestamps |

## Pipeline (5 stages, CLI, fully automatic)

1. **Fetch** (`fetch.py`) — `yt-dlp` downloads the source video + audio to a
   per-run working dir. Accepts a normal URL or a `ytsearch:"query"` term.
2. **Transcribe** (`transcribe.py`) — local `faster-whisper` produces a full
   transcript with **word-level timestamps**.
3. **Select** (`select.py`) — an LLM reads the timestamped transcript and returns
   the **top N moments** (default 6). Each moment: `start`, `end`, a one-line
   `reason`, and a suggested `hook` headline. Boundaries are snapped to clean
   sentence edges from the word timing.
4. **Render** (`render.py` + `captions.py`) — per moment, pure ffmpeg:
   cut `start→end`, **blurred-pad to 9:16** (full 16:9 frame centered over a
   blurred, zoomed fill — nothing cropped out), burn an **ASS karaoke caption**
   file (word-by-word highlight built from the Whisper word times), and overlay
   the **word-wrapped hook headline** at the top. ffmpeg binary is `config.FFMPEG`.
5. **Package** (`metadata.py`) — an LLM writes a **post caption + title + hashtags**
   per clip. Each clip lands in its own folder with `clip_NN.mp4` + `meta.json`.

## Repo layout

```
clip_factory/
  clipper/
    config.py          # model, default N, caption style, paths
    fetch.py           # yt-dlp wrapper (URL or ytsearch:)
    transcribe.py      # faster-whisper -> word-timed transcript
    select.py          # LLM moment-picker -> list[Moment]
    render.py          # ffmpeg crop + ASS captions + hook overlay
    captions.py        # word timestamps -> ASS karaoke file
    metadata.py        # LLM -> caption/title/hashtags
    run_clip.py        # CLI orchestrator: fetch -> ... -> package
    cost_log.py        # per-call API cost logging (JSONL ledger)
  output/<video_id>/clip_NN/ { clip_NN.mp4, meta.json }
  tests/
  .env                 # reuses the existing ANTHROPIC_API_KEY
```

## Data shapes

- **Moment** (from `select.py`): `{ start: float, end: float, reason: str, hook: str }`
- **meta.json** (per clip): `{ index, source_url, start, end, reason, hook,
  caption, title, hashtags: [str], duration }`

## Conventions carried over from TUG

- `python3` (no `python` binary), absolute imports, run via
  `python3 -m clipper.run_clip <url>`.
- **Self-stub on missing data** — a bad moment or failed clip never crashes the
  batch; it is logged and skipped.
- Per-call **API cost logging** to a JSONL ledger.
- `python3 -m pytest tests/ -q` is the contract.

## Error handling

- **Fetch fails** (geo-block / age-gate / removed video) → clear error, exit non-zero.
- **A single clip's render fails** → log + skip, continue rendering the rest.
- Whisper transcription and the two LLM calls are the only slow steps; each
  ffmpeg render is seconds.

## Preview gate (build in two phases)

**Phase 1 — preview:** Build just enough of the pipeline to render **ONE** clip
from a real URL the user provides, so the user can eyeball the crop, caption
style, and hook headline. If the look is wrong, adjust **stage 4 only**.

**Phase 2 — full tool:** Only after the preview is approved, complete the
auto top-N batch run, metadata packaging, and tests.

## Testing

- Unit tests on the deterministic pieces: boundary-snapping in `select`, ASS
  generation from word times in `captions`, and the `meta.json` shape — using a
  small fixture transcript.
- Whisper / LLM / ffmpeg are exercised by an integration smoke run, not unit-mocked.
