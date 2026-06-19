from pathlib import Path

from clipper import render
from clipper.select import Moment
from clipper.transcribe import Word


def test_build_vf_contains_stages():
    vf = render.build_vf("/tmp/c.ass", "/tmp/hook.txt", width=1080, height=1920)
    # blurred-pad reframe: split into blurred bg + full-frame fg, overlaid
    assert "split=2[bg][fg]" in vf
    assert "boxblur" in vf
    assert "scale=1080:1920:force_original_aspect_ratio=increase" in vf
    assert "overlay=(W-w)/2:(H-h)/2" in vf
    assert "ass=" in vf
    assert "drawtext=textfile=" in vf


def test_build_vf_without_hook():
    vf = render.build_vf("/tmp/c.ass", None)
    assert "drawtext" not in vf


def test_wrap_hook_breaks_long_headline():
    wrapped = render.wrap_hook("How They Faked The Moon Landing", width=18)
    assert "\n" in wrapped  # long hook wraps to multiple lines
    assert all(len(line) <= 18 for line in wrapped.split("\n"))
    assert render.wrap_hook("Short Hook") == "Short Hook"  # short stays one line


def test_build_cmd_uses_duration_not_to():
    cmd = render.build_cmd("/in.mp4", 10.0, 25.0, "VF", "/out.mp4")
    assert "-ss" in cmd and "10.000" in cmd
    assert "-t" in cmd and "15.000" in cmd
    assert "-to" not in cmd
    assert cmd[-1] == "/out.mp4"


def test_render_clip_invokes_runner(tmp_path):
    calls = {}

    def fake_run(cmd):
        calls["cmd"] = cmd

    out = render.render_clip(
        "/in.mp4",
        Moment(start=1.0, end=18.0, reason="r", hook="My Hook"),
        [Word(1.0, 1.5, "hi")],
        tmp_path,
        3,
        _run=fake_run,
    )
    assert out == tmp_path / "clip_03.mp4"
    assert (tmp_path / "clip_03.ass").exists()
    assert (tmp_path / "clip_03.hook.txt").read_text() == "My Hook"
    assert "ffmpeg" in calls["cmd"][0]
