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
