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
