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
