import dataclasses
from pathlib import Path

from clipper import config


@dataclasses.dataclass
class FetchResult:
    video_id: str
    title: str
    path: Path


def normalize_source(source: str) -> str:
    """A bare search term (no scheme) becomes a single-result ytsearch query."""
    s = source.strip()
    if s.startswith(("http://", "https://", "ytsearch")):
        return s
    return f"ytsearch1:{s}"


def fetch(source: str, work_dir: Path = config.WORK_DIR, *, _ydl_cls=None) -> FetchResult:
    work_dir.mkdir(parents=True, exist_ok=True)
    query = normalize_source(source)
    opts = {
        "format": "bv*[height<=1080]+ba/b[height<=1080]/b",
        "merge_output_format": "mp4",
        "outtmpl": str(work_dir / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
    }
    cls = _ydl_cls
    if cls is None:
        import yt_dlp

        cls = yt_dlp.YoutubeDL
    with cls(opts) as ydl:
        info = ydl.extract_info(query, download=True)
        if "entries" in info:  # ytsearch returns a playlist-shaped dict
            info = info["entries"][0]
    vid = info["id"]
    return FetchResult(video_id=vid, title=info.get("title", vid), path=work_dir / f"{vid}.mp4")
