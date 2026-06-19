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
