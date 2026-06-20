# Stage-2 v1 — YouTube manual uploader (design)

**Date:** 2026-06-19
**Stage:** 2 (auto-post) — first slice only: manual, single-clip, YouTube-only.
**Status:** approved design, pre-implementation.

## Goal

Give clip_factory a working **upload path**: take one already-rendered clip and push it
to a single YouTube channel the user owns, gated by the `SOURCES.md` rights allowlist.
This proves the posting path end-to-end without building the queue/scheduler/multi-platform
surface (deferred to later Stage-2 work).

## Locked decisions (from brainstorming)

- **One channel, user-owned.** Single OAuth credential, single refresh token.
- **Manual, one clip at a time.** No batch, no scheduler in v1.
- **Private by default.** Uploads land `private`; `--public` flag opts into immediate public.
  The upload becomes a staging step; the user's eyeball stays the final gate.
- **Separate Google Cloud project** for clip_factory (isolated from the TUG project's quota,
  consent screen, and billing).
- **Hard rights gate, no override flag** in v1. Adding a line to `SOURCES.md` *is* the
  deliberate act of confirming rights.

## Constraint: API upload quota

YouTube Data API v3: `videos.insert` costs **1,600 quota units**; default project budget is
**10,000 units/day** → **~6 API uploads/day**. (The separate "Video Uploads per day = 100"
cap is never binding — the query-unit budget runs out first.) Manual web/app uploads do NOT
count against this; only programmatic uploads do. The 6/day ceiling is adjustable later via
the YouTube API audit form, gated on proving the pipeline posts clips worth scaling.

## Module & entrypoint

New module `publish/youtube.py` (the `publish/` dir is already reserved in CLAUDE.md).

```bash
python3 -m publish.youtube output/<vid>/clip_03          # uploads PRIVATE
python3 -m publish.youtube output/<vid>/clip_03 --public # uploads PUBLIC immediately
```

Takes **one clip directory** (folder holding `clip_NN.mp4` + `meta.json`), so it can read
`meta.json` alongside the video. Runs the rights gate, uploads, prints the resulting
`https://youtube.com/watch?v=<id>` URL.

## Auth

- Separate GCP project; **YouTube Data API v3** enabled; OAuth consent screen (External,
  user added as test user); **OAuth client ID type "Desktop app"** → `client_secret.json`.
- Libraries: `google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2`
  (added to requirements).
- First run opens the browser once for consent → stores a **refresh token** locally so later
  uploads are non-interactive.
- Secrets are **gitignored**, in a gitignored `secrets/` dir: `secrets/client_secret.json`,
  `secrets/youtube_token.json`. Paths overridable via `CLIP_YT_CLIENT_SECRET` /
  `CLIP_YT_TOKEN` env vars (mirrors the existing `CLIP_FFMPEG` / `CLIP_MODEL` convention).

## Rights gate

Before any upload, read `meta.json["source"]` and check it against `SOURCES.md`:

- Parse the `## Authorized` section; from each entry pull the channel/URL/handle token
  (the 2nd `—`-delimited field).
- **Authorized** if `meta["source"]` normalize-matches any listed token → proceed.
- **Not authorized** — including any `ytsearch:` source (no verifiable URL) → **hard refuse**,
  exit non-zero, print the rejected source and how to add it to `SOURCES.md`. No silent
  fallback, no `--force`.

## Metadata mapping (`meta.json` → YouTube)

| YouTube field   | Source                                                            |
|-----------------|-------------------------------------------------------------------|
| `title`         | `meta["title"]` (≤80 chars already; YT limit 100)                 |
| `description`   | `meta["caption"]` + blank line + hashtags joined + `#Shorts`      |
| `tags`          | `meta["hashtags"]` with `#` stripped                              |
| `categoryId`    | default `"22"` (People & Blogs), env-overridable `CLIP_YT_CATEGORY` |
| `privacyStatus` | `private` (or `public` with `--public`)                           |

Clips are 9:16 and 20–55s, so appending `#Shorts` files them as Shorts automatically.
Upload uses a **resumable** `videos().insert()`.

## Logging

Append each upload to `logs/uploads.jsonl`:
`{timestamp, source, clip_dir, video_id, privacy}` — local record, daily-quota tally,
and a seed for Stage-3 outcome tracking.

## Testing

`tests/` (run by the `clipper-test` PostToolUse hook):

- Mock the YouTube client exactly like `select`/`metadata` mock `anthropic`.
- Assert: (a) rights gate blocks an unlisted source and any `ytsearch:` source;
  (b) metadata maps correctly (title/description/tags/category/privacy); (c) `private`
  default vs `--public`.
- **No real API calls, no uploads in tests/hooks/CI** — same rule as render.

## Out of scope (deferred)

- Batch upload of a whole `output/<vid>/` folder.
- Scheduled drip / queue / cron.
- TikTok / IG Reels.
- Multi-channel / multi-tenant ("giving other clippers access").
- Quota-increase audit submission.
- Stage-3 earnings/virality tracking (consumes `logs/uploads.jsonl` later).
