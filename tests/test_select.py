from types import SimpleNamespace

from clipper import select
from clipper.transcribe import Transcript, Word


def _words(*spans):
    return [Word(s, e, t) for s, e, t in spans]


def test_snap_bounds_nearest_word_edges():
    words = _words((0.0, 0.5, "a"), (10.0, 10.5, "b"), (40.0, 40.6, "c"))
    s, e = select.snap_bounds(9.8, 40.4, words, min_sec=5, max_sec=120)
    assert s == 10.0
    assert e == 40.6


def test_snap_bounds_enforces_min():
    words = _words((0.0, 0.5, "a"), (1.0, 1.5, "b"))
    s, e = select.snap_bounds(0.0, 1.5, words, min_sec=15, max_sec=90)
    assert e - s == 15


def test_snap_bounds_enforces_max():
    words = _words((0.0, 0.5, "a"), (200.0, 200.5, "b"))
    s, e = select.snap_bounds(0.0, 200.5, words, min_sec=15, max_sec=90)
    assert e - s == 90


def test_timestamped_text_marks_every_n():
    words = _words(*[(i * 1.0, i + 0.4, f" w{i}") for i in range(25)])
    blob = select.timestamped_text(Transcript(words=words), every=12)
    assert blob.count("s] ") == 3  # markers at 0, 12, 24


def test_select_moments_snaps_and_caps(monkeypatch):
    words = _words((0.0, 0.5, "a"), (30.0, 30.5, "b"), (90.0, 90.5, "c"))
    raw = select.MomentList(moments=[
        select.Moment(start=0.1, end=30.4, reason="r1", hook="h1"),
        select.Moment(start=30.0, end=90.4, reason="r2", hook="h2"),
        select.Moment(start=0.0, end=30.0, reason="r3", hook="h3"),
    ])

    class FakeClient:
        class messages:
            @staticmethod
            def parse(**kwargs):
                return SimpleNamespace(
                    parsed_output=raw,
                    usage=SimpleNamespace(input_tokens=10, output_tokens=5),
                )

    got = select.select_moments(Transcript(words=words), n=2, client=FakeClient())
    assert len(got) == 2  # capped to n
    assert got[0].start == 0.0  # snapped to nearest word edge
