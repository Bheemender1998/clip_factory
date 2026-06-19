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
