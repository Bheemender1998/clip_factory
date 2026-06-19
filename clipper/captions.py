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
