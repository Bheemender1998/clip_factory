---
name: make-clips
description: Batch-generate ready-to-post 9:16 clips from a YouTube video. Use when the user says "make clips", "clip this video", "run the batch", or "/make-clips".
---

# make-clips

Generate the top-N clips from a source video, each with karaoke captions, a hook, and meta.json.

## Steps

1. **Rights check (hard gate):** confirm the source is authorized — its channel/creator/campaign must be listed in `SOURCES.md`. If it is not, stop and ask the user to confirm rights before clipping.
2. Activate the venv and run the batch (default N=6; pass the user's count):
   ```bash
   . .venv/bin/activate
   python3 -m clipper.run_clip "<url>" --n <N>
   ```
3. Output lands in `output/<video_id>/clip_NN/{clip_NN.mp4, meta.json}`. Relay the clip count and paths.
4. If clips were skipped (`[skip] clip N failed: ...`), report which and why.
5. Suggest `/preview-clip` first if the user hasn't validated the look for this source.
