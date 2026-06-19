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
