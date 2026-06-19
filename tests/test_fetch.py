from pathlib import Path

from clipper import fetch


def test_normalize_passes_through_urls():
    assert fetch.normalize_source("https://youtu.be/abc") == "https://youtu.be/abc"
    assert fetch.normalize_source("ytsearch3:cats") == "ytsearch3:cats"


def test_normalize_wraps_bare_terms():
    assert fetch.normalize_source("  joe rogan elon  ") == "ytsearch1:joe rogan elon"


class _FakeYDL:
    """Stand-in for yt_dlp.YoutubeDL that records opts and returns a fixed info dict."""

    last_opts = None

    def __init__(self, opts):
        _FakeYDL.last_opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, query, download=True):
        # ytsearch returns a playlist-shaped dict
        if query.startswith("ytsearch"):
            return {"entries": [{"id": "vid123", "title": "Found It"}]}
        return {"id": "vid123", "title": "Direct"}


def test_fetch_returns_result_from_search(tmp_path):
    res = fetch.fetch("some topic", work_dir=tmp_path, _ydl_cls=_FakeYDL)
    assert res.video_id == "vid123"
    assert res.title == "Found It"
    assert res.path == tmp_path / "vid123.mp4"
    assert _FakeYDL.last_opts["noplaylist"] is True


def test_fetch_returns_result_from_url(tmp_path):
    res = fetch.fetch("https://youtu.be/x", work_dir=tmp_path, _ydl_cls=_FakeYDL)
    assert res.video_id == "vid123"
    assert res.title == "Direct"
