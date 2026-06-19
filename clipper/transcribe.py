import dataclasses

from clipper import config


@dataclasses.dataclass
class Word:
    start: float
    end: float
    text: str


@dataclasses.dataclass
class Transcript:
    words: list

    @property
    def text(self) -> str:
        return "".join(w.text for w in self.words)


def words_from_segments(segments) -> list:
    out = []
    for seg in segments:
        for w in (seg.words or []):
            out.append(Word(start=float(w.start), end=float(w.end), text=w.word))
    return out


def transcribe(path, *, _model=None) -> Transcript:
    model = _model
    if model is None:
        from faster_whisper import WhisperModel

        model = WhisperModel(config.WHISPER_MODEL, compute_type=config.WHISPER_COMPUTE)
    segments, _info = model.transcribe(str(path), word_timestamps=True)
    return Transcript(words=words_from_segments(segments))
