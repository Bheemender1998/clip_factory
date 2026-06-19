# clip_factory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A CLI that turns a long YouTube video into 5–8 ready-to-post 9:16 short clips, each with karaoke captions, a hook headline, and a written social caption/title/hashtags.

**Architecture:** A 5-stage pipeline (`fetch → transcribe → select → render → package`) under `clipper/`, mirroring TUG's `engine/` conventions but fully independent. Deterministic units (caption ASS generation, boundary snapping, cost math, meta.json shaping) are unit-tested with TDD; the integration units (yt-dlp, faster-whisper, the Anthropic calls, ffmpeg) are wrapped behind thin, injectable seams and exercised by smoke runs. Build is **preview-gated**: Phase 1 (Tasks 1–7) ships one rendered clip for the user to eyeball before Phase 2 (Tasks 8–9) completes the batch tool.

**Tech Stack:** Python 3 (`python3`), `anthropic` SDK, `yt-dlp`, `faster-whisper`, system `ffmpeg`, `pydantic`, `python-dotenv`, `pytest`.

## Global Constraints

- **`python3`, never `python`** — this machine has no `python` binary.
- **All imports are absolute `clipper.*`** — run via `python3 -m clipper.run_clip <url>`.
- **Single virtualenv** — faster-whisper + ffmpeg + anthropic coexist; there is no Remotion/Kokoro split here. (TUG's two-venv rule does NOT apply to this repo.)
- **`ffmpeg` must be on PATH** — system binary, not a pip package.
- **Anthropic model id is exactly `claude-opus-4-8`** (configurable via `CLIP_MODEL`; the documented cheap high-volume alternative is `claude-sonnet-4-6`). Never append a date suffix.
- **Pricing ($/1M tokens, input/output):** `claude-opus-4-8` = (5.0, 25.0), `claude-sonnet-4-6` = (3.0, 15.0), `claude-haiku-4-5` = (1.0, 5.0).
- **Structured LLM calls use `client.messages.parse(..., output_format=<PydanticModel>)`** and read `resp.parsed_output`. The selector additionally passes `thinking={"type": "adaptive"}`.
- **Self-stub on failure** — a single bad moment or failed clip render is logged and skipped; it never aborts the batch.
- **`python3 -m pytest tests/ -q` is the contract** — run it after every task.
- **The `ANTHROPIC_API_KEY` is read from `.env`** (gitignored) via `python-dotenv`; never hardcode it.

---

### Task 1: Project scaffold — config, cost ledger, packaging

**Files:**
- Create: `clipper/__init__.py` (empty)
- Create: `clipper/config.py`
- Create: `clipper/cost_log.py`
- Create: `requirements.txt`
- Create: `tests/__init__.py` (empty)
- Create: `tests/test_cost_log.py`

**Interfaces:**
- Produces: `config.MODEL`, `config.PRICING`, `config.ROOT`, `config.OUTPUT_DIR`, `config.WORK_DIR`, `config.DEFAULT_CLIP_COUNT`, `config.WHISPER_MODEL`, `config.WHISPER_COMPUTE`, `config.TARGET_W`, `config.TARGET_H`, `config.MIN_CLIP_SEC`, `config.MAX_CLIP_SEC`.
- Produces: `cost_log.cost_for(model: str, input_tokens: int, output_tokens: int) -> float`, `cost_log.log_call(stage: str, model: str, usage, *, ledger: Path = LEDGER) -> dict`.

- [ ] **Step 1: Write `requirements.txt`**

```
anthropic
yt-dlp
faster-whisper
pydantic
python-dotenv
pytest
```

- [ ] **Step 2: Create the empty package markers**

Create `clipper/__init__.py` and `tests/__init__.py` as empty files.

- [ ] **Step 3: Write `clipper/config.py`**

```python
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
WORK_DIR = ROOT / "work"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = os.environ.get("CLIP_MODEL", "claude-opus-4-8")
DEFAULT_CLIP_COUNT = int(os.environ.get("CLIP_COUNT", "6"))

WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base.en")
WHISPER_COMPUTE = os.environ.get("WHISPER_COMPUTE", "int8")

# 9:16 render target
TARGET_W = 1080
TARGET_H = 1920
MIN_CLIP_SEC = 15.0
MAX_CLIP_SEC = 90.0

# $ per 1M tokens: (input, output)
PRICING = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}
```

- [ ] **Step 4: Write the failing test `tests/test_cost_log.py`**

```python
import json
from types import SimpleNamespace

from clipper import cost_log


def test_cost_for_opus():
    # 1M input @ $5 + 1M output @ $25 = $30
    assert cost_log.cost_for("claude-opus-4-8", 1_000_000, 1_000_000) == 30.0


def test_cost_for_strips_dated_suffix():
    assert cost_log.cost_for("claude-haiku-4-5-20251001", 1_000_000, 0) == 1.0


def test_cost_for_unknown_model_is_zero():
    assert cost_log.cost_for("mystery-model", 1_000_000, 1_000_000) == 0.0


def test_log_call_appends_jsonl(tmp_path):
    ledger = tmp_path / "api-cost.jsonl"
    usage = SimpleNamespace(input_tokens=1_000_000, output_tokens=0)
    rec = cost_log.log_call("select", "claude-opus-4-8", usage, ledger=ledger)
    assert rec["cost_usd"] == 5.0
    assert rec["stage"] == "select"
    line = json.loads(ledger.read_text().strip())
    assert line["model"] == "claude-opus-4-8"
    assert line["input_tokens"] == 1_000_000
```

- [ ] **Step 5: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_cost_log.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'clipper.cost_log'`

- [ ] **Step 6: Write `clipper/cost_log.py`**

```python
import json
import re
import time
from pathlib import Path

from clipper import config

LEDGER = config.ROOT / "logs" / "api-cost.jsonl"


def _pricing_key(model: str) -> str:
    """Strip a dated -YYYYMMDD suffix so 'claude-haiku-4-5-20251001' resolves."""
    return re.sub(r"-\d{8}$", "", model)


def cost_for(model: str, input_tokens: int, output_tokens: int) -> float:
    inp, out = config.PRICING.get(_pricing_key(model), (0.0, 0.0))
    return (input_tokens / 1_000_000) * inp + (output_tokens / 1_000_000) * out


def log_call(stage: str, model: str, usage, *, ledger: Path = LEDGER) -> dict:
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    rec = {
        "ts": time.time(),
        "stage": stage,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(cost_for(model, input_tokens, output_tokens), 6),
    }
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_cost_log.py -q`
Expected: PASS (4 passed)

- [ ] **Step 8: Commit**

```bash
git add clipper/__init__.py clipper/config.py clipper/cost_log.py requirements.txt tests/__init__.py tests/test_cost_log.py
git commit -m "feat(scaffold): config + API cost ledger"
```

---

### Task 2: Fetch — yt-dlp wrapper

**Files:**
- Create: `clipper/fetch.py`
- Create: `tests/test_fetch.py`

**Interfaces:**
- Consumes: `config.WORK_DIR`.
- Produces: `fetch.normalize_source(source: str) -> str`; `fetch.FetchResult(video_id: str, title: str, path: pathlib.Path)`; `fetch.fetch(source: str, work_dir=config.WORK_DIR, *, _ydl_cls=None) -> FetchResult`.

- [ ] **Step 1: Write the failing test `tests/test_fetch.py`**

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_fetch.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'clipper.fetch'`

- [ ] **Step 3: Write `clipper/fetch.py`**

```python
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_fetch.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add clipper/fetch.py tests/test_fetch.py
git commit -m "feat(fetch): yt-dlp wrapper with ytsearch fallback"
```

---

### Task 3: Transcribe — faster-whisper → word-timed transcript

**Files:**
- Create: `clipper/transcribe.py`
- Create: `tests/test_transcribe.py`

**Interfaces:**
- Consumes: `config.WHISPER_MODEL`, `config.WHISPER_COMPUTE`.
- Produces: `transcribe.Word(start: float, end: float, text: str)`; `transcribe.Transcript(words: list[Word])` with a `.text` property; `transcribe.words_from_segments(segments) -> list[Word]`; `transcribe.transcribe(path, *, _model=None) -> Transcript`.

- [ ] **Step 1: Write the failing test `tests/test_transcribe.py`**

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_transcribe.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'clipper.transcribe'`

- [ ] **Step 3: Write `clipper/transcribe.py`**

```python
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_transcribe.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add clipper/transcribe.py tests/test_transcribe.py
git commit -m "feat(transcribe): faster-whisper word-timed transcript"
```

---

### Task 4: Captions — words → ASS karaoke file

**Files:**
- Create: `clipper/captions.py`
- Create: `tests/test_captions.py`

**Interfaces:**
- Consumes: `transcribe.Word`, `config.TARGET_W`, `config.TARGET_H`.
- Produces: `captions._ass_timestamp(t: float) -> str`; `captions.build_ass(words, clip_start, clip_end, *, words_per_line=4, width=config.TARGET_W, height=config.TARGET_H, font="Arial", fontsize=96) -> str`.

- [ ] **Step 1: Write the failing test `tests/test_captions.py`**

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_captions.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'clipper.captions'`

- [ ] **Step 3: Write `clipper/captions.py`**

```python
from clipper import config
from clipper.transcribe import Word

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,{font},{fontsize},&H0000FFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,4,2,2,80,80,260,1

[Events]
Format: Layer, Start, End, Style, MarginL, MarginR, MarginV, Effect, Text
"""


def _ass_timestamp(t: float) -> str:
    if t < 0:
        t = 0.0
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def build_ass(words, clip_start, clip_end, *, words_per_line=4,
              width=config.TARGET_W, height=config.TARGET_H, font="Arial", fontsize=96) -> str:
    rel = []
    for w in words:
        if w.end <= clip_start or w.start >= clip_end:
            continue
        rel.append(Word(start=max(0.0, w.start - clip_start),
                        end=max(0.0, w.end - clip_start),
                        text=w.text.strip()))
    lines = [rel[i:i + words_per_line] for i in range(0, len(rel), words_per_line)]
    events = []
    for line in lines:
        if not line:
            continue
        start = line[0].start
        end = line[-1].end
        chunks = []
        for w in line:
            dur_cs = max(1, int(round((w.end - w.start) * 100)))
            chunks.append(f"{{\\k{dur_cs}}}{w.text} ")
        text = "".join(chunks).strip()
        events.append(
            f"Dialogue: 0,{_ass_timestamp(start)},{_ass_timestamp(end)},Karaoke,80,80,260,,{text}"
        )
    header = ASS_HEADER.format(w=width, h=height, font=font, fontsize=fontsize)
    return header + "\n".join(events) + "\n"
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_captions.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add clipper/captions.py tests/test_captions.py
git commit -m "feat(captions): word-timed ASS karaoke generation"
```

---

### Task 5: Select — LLM moment picker + boundary snapping

**Files:**
- Create: `clipper/select.py`
- Create: `tests/test_select.py`

**Interfaces:**
- Consumes: `config.MODEL`, `config.DEFAULT_CLIP_COUNT`, `config.MIN_CLIP_SEC`, `config.MAX_CLIP_SEC`, `transcribe.Transcript`, `transcribe.Word`, `cost_log.log_call`.
- Produces: `select.Moment` (pydantic: `start: float, end: float, reason: str, hook: str`); `select.MomentList` (pydantic: `moments: list[Moment]`); `select.timestamped_text(transcript, *, every=12) -> str`; `select.snap_bounds(start, end, words, *, min_sec, max_sec) -> tuple[float, float]`; `select.select_moments(transcript, *, n=config.DEFAULT_CLIP_COUNT, model=config.MODEL, client=None) -> list[Moment]`.

- [ ] **Step 1: Write the failing test `tests/test_select.py`**

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_select.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'clipper.select'`

- [ ] **Step 3: Write `clipper/select.py`**

```python
from pydantic import BaseModel

from clipper import config, cost_log


class Moment(BaseModel):
    start: float
    end: float
    reason: str
    hook: str


class MomentList(BaseModel):
    moments: list[Moment]


def timestamped_text(transcript, *, every=12) -> str:
    out = []
    for i, w in enumerate(transcript.words):
        if i % every == 0:
            out.append(f"\n[{w.start:.1f}s] ")
        out.append(w.text)
    return "".join(out)


def snap_bounds(start, end, words, *, min_sec, max_sec):
    if not words:
        return start, end
    s = min((w.start for w in words), key=lambda x: abs(x - start))
    e = min((w.end for w in words), key=lambda x: abs(x - end))
    if e - s < min_sec:
        e = s + min_sec
    if e - s > max_sec:
        e = s + max_sec
    return s, e


def select_moments(transcript, *, n=config.DEFAULT_CLIP_COUNT, model=config.MODEL, client=None) -> list:
    if client is None:
        import anthropic

        client = anthropic.Anthropic()
    body = timestamped_text(transcript)
    prompt = (
        "You are a viral short-form video editor. From this timestamped transcript, "
        f"pick the {n} best self-contained moments to cut as vertical short clips. "
        "Each moment needs: start and end in SECONDS (use the [Ns] markers as your guide), "
        "a one-line reason it will perform, and a punchy hook headline of at most 8 words. "
        f"Clips must be between {config.MIN_CLIP_SEC:.0f} and {config.MAX_CLIP_SEC:.0f} seconds.\n\n"
        f"TRANSCRIPT:\n{body}"
    )
    resp = client.messages.parse(
        model=model,
        max_tokens=4000,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
        output_format=MomentList,
    )
    cost_log.log_call("select", model, resp.usage)
    moments = resp.parsed_output.moments[:n]
    snapped = []
    for m in moments:
        s, e = snap_bounds(m.start, m.end, transcript.words,
                           min_sec=config.MIN_CLIP_SEC, max_sec=config.MAX_CLIP_SEC)
        snapped.append(Moment(start=s, end=e, reason=m.reason, hook=m.hook))
    return snapped
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_select.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add clipper/select.py tests/test_select.py
git commit -m "feat(select): LLM moment picker with boundary snapping"
```

---

### Task 6: Render — ffmpeg crop + ASS burn + hook overlay

**Files:**
- Create: `clipper/render.py`
- Create: `tests/test_render.py`

**Interfaces:**
- Consumes: `config.TARGET_W`, `config.TARGET_H`, `captions.build_ass`, `select.Moment`, `transcribe.Word`.
- Produces: `render._fp(path) -> str` (filtergraph path escaper); `render.build_vf(ass_path, hook_txt_path, *, width=config.TARGET_W, height=config.TARGET_H) -> str`; `render.build_cmd(input_path, start, end, vf, out_path) -> list[str]`; `render.render_clip(input_path, moment, words, out_dir, index, *, _run=None) -> pathlib.Path`.

- [ ] **Step 1: Write the failing test `tests/test_render.py`**

```python
from pathlib import Path

from clipper import render
from clipper.select import Moment
from clipper.transcribe import Word


def test_build_vf_contains_stages():
    vf = render.build_vf("/tmp/c.ass", "/tmp/hook.txt", width=1080, height=1920)
    assert "crop=ih*9/16:ih" in vf
    assert "scale=1080:1920" in vf
    assert "ass=" in vf
    assert "drawtext=textfile=" in vf


def test_build_vf_without_hook():
    vf = render.build_vf("/tmp/c.ass", None)
    assert "drawtext" not in vf


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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_render.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'clipper.render'`

- [ ] **Step 3: Write `clipper/render.py`**

```python
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
        "ffmpeg", "-y",
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_render.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add clipper/render.py tests/test_render.py
git commit -m "feat(render): ffmpeg 9:16 crop + ASS captions + hook overlay"
```

---

### Task 7: Preview CLI — render ONE clip end-to-end (PREVIEW GATE)

**Files:**
- Create: `clipper/run_clip.py`
- Create: `run_clip.py` (root shim)
- Create: `tests/test_run_clip_preview.py`

**Interfaces:**
- Consumes: `fetch.fetch`, `transcribe.transcribe`, `select.select_moments`, `render.render_clip`, `config.OUTPUT_DIR`.
- Produces: `run_clip.run_preview(source: str) -> pathlib.Path`; `run_clip.main(argv=None) -> int` (CLI entrypoint accepting `<source>` and `--preview`).

- [ ] **Step 1: Write the failing test `tests/test_run_clip_preview.py`**

```python
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
    assert out == tmp_path / "vid9" / "clip_01.mp4"


def test_main_preview_returns_zero(monkeypatch):
    monkeypatch.setattr(run_clip, "run_preview", lambda src: Path("/x/clip_01.mp4"))
    assert run_clip.main(["some-url", "--preview"]) == 0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_run_clip_preview.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'clipper.run_clip'`

- [ ] **Step 3: Write `clipper/run_clip.py`**

```python
import argparse
import sys
from pathlib import Path

from clipper import config, fetch, render, select, transcribe


def run_preview(source: str) -> Path:
    fetched = fetch.fetch(source)
    tx = transcribe.transcribe(fetched.path)
    moments = select.select_moments(tx, n=1)
    if not moments:
        raise SystemExit("No moments found in source.")
    out_dir = config.OUTPUT_DIR / fetched.video_id
    out = render.render_clip(fetched.path, moments[0], tx.words, out_dir, 1)
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="clipper")
    parser.add_argument("source", help="YouTube URL or search term")
    parser.add_argument("--preview", action="store_true",
                        help="render only the single best clip")
    args = parser.parse_args(argv)
    if args.preview:
        out = run_preview(args.source)
        print(f"Preview clip: {out}")
        return 0
    # Full batch path is added in Task 9.
    raise SystemExit("Full batch mode not implemented yet — use --preview.")


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Write the root shim `run_clip.py`**

```python
from clipper.run_clip import main

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_run_clip_preview.py -q`
Expected: PASS (2 passed)

- [ ] **Step 6: Run the full suite**

Run: `python3 -m pytest tests/ -q`
Expected: PASS (all tasks 1–7 green)

- [ ] **Step 7: Commit**

```bash
git add clipper/run_clip.py run_clip.py tests/test_run_clip_preview.py
git commit -m "feat(cli): preview path renders one clip end-to-end"
```

- [ ] **Step 8: PREVIEW GATE — real smoke run**

Install deps in a venv (`python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`), confirm `ffmpeg -version` works, put the `ANTHROPIC_API_KEY` in `.env`, then run a real preview against a short public video the user provides:

```bash
python3 -m clipper.run_clip "<USER-PROVIDED-YOUTUBE-URL>" --preview
```

Open the printed `clip_01.mp4`. **STOP here and have the user eyeball the crop, caption style, and hook headline before starting Phase 2.** If the look is wrong, adjust Task 6 (`build_vf` / `captions.build_ass`) only and re-run; do not proceed to Task 8 until the preview is approved.

---

### Task 8: Metadata — LLM caption / title / hashtags

**Files:**
- Create: `clipper/metadata.py`
- Create: `tests/test_metadata.py`

**Interfaces:**
- Consumes: `config.MODEL`, `cost_log.log_call`.
- Produces: `metadata.ClipMeta` (pydantic: `title: str, caption: str, hashtags: list[str]`); `metadata.write_metadata(clip_text: str, hook: str, *, model=config.MODEL, client=None) -> ClipMeta`.

- [ ] **Step 1: Write the failing test `tests/test_metadata.py`**

```python
from types import SimpleNamespace

from clipper import metadata


def test_write_metadata_returns_parsed(monkeypatch):
    result = metadata.ClipMeta(title="T", caption="C", hashtags=["#a", "#b"])

    class FakeClient:
        class messages:
            @staticmethod
            def parse(**kwargs):
                assert kwargs["output_format"] is metadata.ClipMeta
                return SimpleNamespace(
                    parsed_output=result,
                    usage=SimpleNamespace(input_tokens=5, output_tokens=3),
                )

    got = metadata.write_metadata("a clip about cats", "Cats Win", client=FakeClient())
    assert got.title == "T"
    assert got.hashtags == ["#a", "#b"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_metadata.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'clipper.metadata'`

- [ ] **Step 3: Write `clipper/metadata.py`**

```python
from pydantic import BaseModel

from clipper import config, cost_log


class ClipMeta(BaseModel):
    title: str
    caption: str
    hashtags: list[str]


def write_metadata(clip_text: str, hook: str, *, model=config.MODEL, client=None) -> ClipMeta:
    if client is None:
        import anthropic

        client = anthropic.Anthropic()
    prompt = (
        "Write social post copy for this short video clip so it performs on TikTok / Reels / Shorts.\n"
        f"Hook headline shown on screen: {hook!r}\n"
        f"Clip transcript: {clip_text!r}\n\n"
        "Return a punchy title (<=80 chars), a 1-2 sentence caption, and 4-6 relevant hashtags "
        "(each starting with #)."
    )
    resp = client.messages.parse(
        model=model,
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
        output_format=ClipMeta,
    )
    cost_log.log_call("metadata", model, resp.usage)
    return resp.parsed_output
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_metadata.py -q`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add clipper/metadata.py tests/test_metadata.py
git commit -m "feat(metadata): LLM caption/title/hashtags per clip"
```

---

### Task 9: Full batch orchestrator — top-N render + package, self-stub skip

**Files:**
- Modify: `clipper/run_clip.py` (add `clip_transcript`, `build_meta`, `run_batch`; wire `main` non-preview path)
- Create: `tests/test_run_clip_batch.py`

**Interfaces:**
- Consumes: everything above plus `metadata.write_metadata`, `config.DEFAULT_CLIP_COUNT`.
- Produces: `run_clip.clip_transcript(transcript, start, end) -> str`; `run_clip.build_meta(index, source, moment, meta, duration) -> dict`; `run_clip.run_batch(source, *, n=config.DEFAULT_CLIP_COUNT) -> list[pathlib.Path]`.

- [ ] **Step 1: Write the failing test `tests/test_run_clip_batch.py`**

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_run_clip_batch.py -q`
Expected: FAIL with `AttributeError: module 'clipper.run_clip' has no attribute 'clip_transcript'`

- [ ] **Step 3: Add `metadata` + `json` imports and the batch functions to `clipper/run_clip.py`**

Add `import json` at the top, add `metadata` to the existing `from clipper import ...` line, and insert these functions before `main`:

```python
def clip_transcript(transcript, start, end) -> str:
    return " ".join(
        w.text.strip() for w in transcript.words if w.start >= start and w.end <= end
    ).strip()


def build_meta(index, source, moment, meta, duration) -> dict:
    return {
        "index": index,
        "source": source,
        "start": round(moment.start, 3),
        "end": round(moment.end, 3),
        "duration": round(duration, 3),
        "reason": moment.reason,
        "hook": moment.hook,
        "title": meta.title,
        "caption": meta.caption,
        "hashtags": meta.hashtags,
    }


def run_batch(source: str, *, n=config.DEFAULT_CLIP_COUNT) -> list:
    fetched = fetch.fetch(source)
    tx = transcribe.transcribe(fetched.path)
    moments = select.select_moments(tx, n=n)
    base = config.OUTPUT_DIR / fetched.video_id
    outs = []
    for i, moment in enumerate(moments, start=1):
        clip_dir = base / f"clip_{i:02d}"
        try:
            out = render.render_clip(fetched.path, moment, tx.words, clip_dir, i)
            text = clip_transcript(tx, moment.start, moment.end)
            meta = metadata.write_metadata(text, moment.hook)
            payload = build_meta(i, source, moment, meta, moment.end - moment.start)
            (clip_dir / "meta.json").write_text(json.dumps(payload, indent=2))
            outs.append(out)
        except Exception as exc:  # self-stub: never abort the batch on one bad clip
            print(f"[skip] clip {i} failed: {exc}")
    return outs
```

- [ ] **Step 4: Wire the non-preview branch of `main`**

Replace the `raise SystemExit("Full batch mode not implemented yet — use --preview.")` line and add an `--n` argument. The argument block and dispatch become:

```python
    parser.add_argument("--preview", action="store_true",
                        help="render only the single best clip")
    parser.add_argument("--n", type=int, default=config.DEFAULT_CLIP_COUNT,
                        help="number of clips to produce in batch mode")
    args = parser.parse_args(argv)
    if args.preview:
        out = run_preview(args.source)
        print(f"Preview clip: {out}")
        return 0
    outs = run_batch(args.source, n=args.n)
    print(f"Rendered {len(outs)} clips:")
    for o in outs:
        print(f"  {o}")
    return 0
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_run_clip_batch.py -q`
Expected: PASS (3 passed)

- [ ] **Step 6: Run the full suite**

Run: `python3 -m pytest tests/ -q`
Expected: PASS (every task green)

- [ ] **Step 7: Real batch smoke run**

```bash
python3 -m clipper.run_clip "<USER-PROVIDED-YOUTUBE-URL>" --n 6
```

Confirm `output/<video_id>/clip_01..06/` each contain a `clip_NN.mp4` + `meta.json`, and `logs/api-cost.jsonl` has `select` + `metadata` entries.

- [ ] **Step 8: Commit**

```bash
git add clipper/run_clip.py tests/test_run_clip_batch.py
git commit -m "feat(cli): batch top-N render + metadata packaging with self-stub skip"
```
