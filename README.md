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

## Publishing (Stage 2 — YouTube, manual)

Upload one rendered clip to your YouTube channel (private by default; `--public` to go live):

```bash
python3 -m publish.youtube output/<vid>/clip_03
```

First run opens a browser once for Google OAuth consent and caches a refresh token at
`secrets/youtube_token.json`. Requires `secrets/client_secret.json` (a Desktop-app OAuth
client from a Google Cloud project with the YouTube Data API v3 enabled). The clip's
`source` must be listed in `SOURCES.md` or the upload is refused. API uploads are capped
at ~6/day by the default 10,000-unit YouTube quota.

## Docs
- `CLAUDE.md` — conventions, hard rules, gate discipline.
- `docs/execution-plan.md` — staged roadmap.
- `docs/adr/` — decision records.
- `SOURCES.md` — authorized-source allowlist (rights gate).
