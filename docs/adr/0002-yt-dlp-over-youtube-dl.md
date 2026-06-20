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
