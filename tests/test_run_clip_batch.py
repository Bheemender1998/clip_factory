import json
from pathlib import Path
from types import SimpleNamespace

from clipper import run_clip
from clipper.fetch import FetchResult
from clipper.metadata import ClipMeta
from clipper.select import Moment
from clipper.transcribe import Transcript, Word


def test_clip_transcript_window():
    words = [Word(0.0, 0.5, " a"), Word(10.0, 10.5, " b"), Word(20.0, 20.5, " c")]
    assert run_clip.clip_transcript(Transcript(words=words), 9.0, 21.0) == "b c"


def test_build_meta_shape():
    m = Moment(start=1.0, end=17.0, reason="r", hook="h")
    meta = ClipMeta(title="T", caption="C", hashtags=["#x"])
    d = run_clip.build_meta(2, "http://src", m, meta, 16.0)
    assert d == {
        "index": 2, "source": "http://src", "start": 1.0, "end": 17.0,
        "duration": 16.0, "reason": "r", "hook": "h",
        "title": "T", "caption": "C", "hashtags": ["#x"],
    }


def test_run_batch_skips_failed_clip(monkeypatch, tmp_path):
    monkeypatch.setattr(run_clip.config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(run_clip, "fetch",
                        SimpleNamespace(fetch=lambda src: FetchResult("vidB", "T", Path("/in.mp4"))))
    monkeypatch.setattr(run_clip, "transcribe",
                        SimpleNamespace(transcribe=lambda p: Transcript(words=[Word(0.0, 0.5, " hi")])))
    moments = [
        Moment(start=0.0, end=16.0, reason="r1", hook="h1"),
        Moment(start=20.0, end=36.0, reason="r2", hook="h2"),
    ]
    monkeypatch.setattr(run_clip, "select",
                        SimpleNamespace(select_moments=lambda t, n: moments))
    monkeypatch.setattr(run_clip, "metadata",
                        SimpleNamespace(write_metadata=lambda text, hook: ClipMeta(title="T", caption="C", hashtags=["#a"])))

    def flaky_render(input_path, moment, words, out_dir, index):
        if index == 1:
            raise RuntimeError("ffmpeg blew up")
        out = Path(out_dir) / f"clip_{index:02d}" / f"clip_{index:02d}.mp4"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("fake")
        return out

    monkeypatch.setattr(run_clip, "render", SimpleNamespace(render_clip=flaky_render))

    outs = run_clip.run_batch("src", n=2)
    assert len(outs) == 1  # clip 1 failed and was skipped; clip 2 survived
    meta_file = tmp_path / "vidB" / "clip_02" / "meta.json"
    assert json.loads(meta_file.read_text())["index"] == 2
