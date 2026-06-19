import subprocess
from pathlib import Path

from clipper import captions, config


def _fp(path) -> str:
    """Escape a path for use inside an ffmpeg filtergraph argument."""
    s = str(path)
    s = s.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    return s


def build_vf(ass_path, hook_txt_path, *, width=config.TARGET_W, height=config.TARGET_H) -> str:
    parts = ["crop=ih*9/16:ih", f"scale={width}:{height}", f"ass={_fp(ass_path)}"]
    if hook_txt_path is not None:
        parts.append(
            "drawtext=textfile=" + _fp(hook_txt_path)
            + ":fontcolor=white:fontsize=72:borderw=4:bordercolor=black"
            + ":x=(w-text_w)/2:y=140:line_spacing=8"
        )
    return ",".join(parts)


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
    hook_path.write_text(moment.hook)

    vf = build_vf(ass_path, hook_path)
    cmd = build_cmd(input_path, moment.start, moment.end, vf, out_path)

    run = _run if _run is not None else (lambda c: subprocess.run(c, check=True))
    run(cmd)
    return out_path
