from types import SimpleNamespace

from clipper import transcribe


def _seg(words):
    return SimpleNamespace(words=[SimpleNamespace(start=s, end=e, word=w) for s, e, w in words])


def test_words_from_segments_flattens():
    segs = [_seg([(0.0, 0.5, " Hello"), (0.5, 1.0, " world")]), _seg([(1.0, 1.4, " again")])]
    words = transcribe.words_from_segments(segs)
    assert [w.text for w in words] == [" Hello", " world", " again"]
    assert words[1].start == 0.5 and words[1].end == 1.0


def test_words_from_segments_tolerates_no_words():
    assert transcribe.words_from_segments([SimpleNamespace(words=None)]) == []


def test_transcript_text_joins_words():
    t = transcribe.Transcript(words=[transcribe.Word(0, 1, " Hi"), transcribe.Word(1, 2, " there")])
    assert t.text == " Hi there"


def test_transcribe_uses_injected_model():
    class FakeModel:
        def transcribe(self, path, word_timestamps=True):
            return [_seg([(0.0, 0.4, " yo")])], SimpleNamespace()

    t = transcribe.transcribe("/tmp/x.mp4", _model=FakeModel())
    assert t.text == " yo"
