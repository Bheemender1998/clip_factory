import json
import sys
from collections import defaultdict
from pathlib import Path

from clipper import config

LEDGER = config.ROOT / "logs" / "api-cost.jsonl"


def load_records(ledger=LEDGER) -> list:
    ledger = Path(ledger)
    if not ledger.exists():
        return []
    out = []
    for line in ledger.read_text().splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def summarize(records) -> dict:
    by_stage = defaultdict(
        lambda: {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    )
    total = 0.0
    for r in records:
        s = by_stage[r.get("stage", "?")]
        s["calls"] += 1
        s["input_tokens"] += r.get("input_tokens", 0)
        s["output_tokens"] += r.get("output_tokens", 0)
        s["cost_usd"] += r.get("cost_usd", 0.0)
        total += r.get("cost_usd", 0.0)
    return {"by_stage": dict(by_stage), "total_cost": round(total, 6)}


def format_report(summary) -> str:
    lines = [f"{'stage':<12} {'calls':>5} {'in_tok':>9} {'out_tok':>9} {'cost_usd':>11}"]
    for stage, s in sorted(summary["by_stage"].items()):
        lines.append(
            f"{stage:<12} {s['calls']:>5} {s['input_tokens']:>9} "
            f"{s['output_tokens']:>9} {s['cost_usd']:>11.4f}"
        )
    lines.append(f"{'TOTAL':<12} {'':>5} {'':>9} {'':>9} {summary['total_cost']:>11.4f}")
    return "\n".join(lines)


def main(argv=None) -> int:
    print(format_report(summarize(load_records())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
