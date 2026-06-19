import sys
from pathlib import Path
from types import SimpleNamespace

from clipper import run_clip
from clipper.fetch import FetchResult
from clipper.select import Moment
from clipper.transcribe import Transcript, Word


def test_run_preview_wires_the_stages(monkeypatch, tmp_path):
    monkeypatch.setattr(run_clip.config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(run_clip, "fetch",
                        SimpleNamespace(fetch=lambda src: FetchResult("vid9", "T", Path("/in.mp4"))))
    monkeypatch.setattr(run_clip, "transcribe",
                        SimpleNamespace(transcribe=lambda p: Transcript(words=[Word(0.0, 0.5, "hi")])))
    monkeypatch.setattr(run_clip, "select",
                        SimpleNamespace(select_moments=lambda t, n: [Moment(start=0.0, end=16.0, reason="r", hook="h")]))

    captured = {}

    def fake_render_clip(input_path, moment, words, out_dir, index):
        out = Path(out_dir) / f"clip_{index:02d}.mp4"
        captured["n_requested"] = 1
        return out

    monkeypatch.setattr(run_clip, "render",
                        SimpleNamespace(render_clip=fake_render_clip))

    out = run_clip.run_preview("anything")
    assert out == tmp_path / "vid9" / "clip_01" / "clip_01.mp4"


def test_main_preview_returns_zero(monkeypatch):
    monkeypatch.setattr(run_clip, "run_preview", lambda src: Path("/x/clip_01.mp4"))
    assert run_clip.main(["some-url", "--preview"]) == 0
