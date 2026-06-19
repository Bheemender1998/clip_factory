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
