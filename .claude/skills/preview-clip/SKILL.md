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
