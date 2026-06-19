from clipper import captions
from clipper.transcribe import Word


def test_ass_timestamp_format():
    assert captions._ass_timestamp(1.5) == "0:00:01.50"
    assert captions._ass_timestamp(0.0) == "0:00:00.00"
    assert captions._ass_timestamp(-3.0) == "0:00:00.00"
    assert captions._ass_timestamp(3661.25) == "1:01:01.25"


def test_build_ass_has_header_and_dialogue():
    words = [Word(0.0, 0.5, "Hello"), Word(0.5, 1.0, "world")]
    out = captions.build_ass(words, 0.0, 2.0, words_per_line=4)
    assert "[Events]" in out
    assert "Style: Karaoke" in out
    assert out.count("Dialogue:") == 1
    assert "\\k" in out  # karaoke timing tags present


def test_build_ass_rebases_to_clip_start_and_filters_window():
    # word at 10-10.5 inside a clip starting at 10 -> rebased to 0-0.5
    words = [Word(5.0, 5.5, "before"), Word(10.0, 10.5, "inside")]
    out = captions.build_ass(words, 10.0, 12.0)
    assert "inside" in out
    assert "before" not in out
    assert "0:00:00.00" in out  # rebased start


def test_build_ass_splits_lines():
    words = [Word(i * 0.5, i * 0.5 + 0.4, f"w{i}") for i in range(9)]
    out = captions.build_ass(words, 0.0, 10.0, words_per_line=4)
    assert out.count("Dialogue:") == 3  # 4 + 4 + 1
