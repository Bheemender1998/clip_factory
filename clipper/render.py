import subprocess
import textwrap
from pathlib import Path

from clipper import captions, config


def _fp(path) -> str:
    """Escape a path for use inside an ffmpeg filtergraph argument."""
    s = str(path)
    s = s.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    return s


def wrap_hook(text, *, width=18) -> str:
    """Word-wrap the hook headline so it fits the 9:16 frame width."""
    text = (text or "").strip()
    if not text:
        return text
    return textwrap.fill(text, width=width)


def build_vf(ass_path, hook_txt_path, *, width=config.TARGET_W, height=config.TARGET_H) -> str:
    # Blurred-pad reframe: the full 16:9 frame is centered (nothing cropped out)
    # over a blurred, zoomed copy of itself that fills the 9:16 canvas.
    chain = (
        "split=2[bg][fg];"
        f"[bg]scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},boxblur=24:2[bgb];"
        f"[fg]scale={width}:-2[fgs];"
        "[bgb][fgs]overlay=(W-w)/2:(H-h)/2,"
        f"ass={_fp(ass_path)}"
    )
    if hook_txt_path is not None:
        chain += (
            ",drawtext=textfile=" + _fp(hook_txt_path)
            + ":fontcolor=white:fontsize=64:text_align=C"
            + ":box=1:boxcolor=black@0.5:boxborderw=16"
            + ":x=(w-text_w)/2:y=90:line_spacing=10"
        )
    return chain


def build_cmd(input_path, start, end, vf, out_path) -> list:
    return [
        config.FFMPEG, "-y",
        "-ss", f"{start:.3f}",
        "-i", str(input_path),
        "-t", f"{end - start:.3f}",
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(out_path),
    ]


def render_clip(input_path, moment, words, out_dir, index, *, _run=None) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"clip_{index:02d}"
    ass_path = out_dir / f"{stem}.ass"
    hook_path = out_dir / f"{stem}.hook.txt"
    out_path = out_dir / f"{stem}.mp4"

    ass_path.write_text(captions.build_ass(words, moment.start, moment.end))
    hook_path.write_text(wrap_hook(moment.hook))

    vf = build_vf(ass_path, hook_path)
    cmd = build_cmd(input_path, moment.start, moment.end, vf, out_path)

    run = _run if _run is not None else (lambda c: subprocess.run(c, check=True))
    run(cmd)
    return out_path
