import json

from clipper import cost_report


def _write(ledger, rows):
    ledger.write_text("\n".join(json.dumps(r) for r in rows) + "\n")


def test_load_records_skips_blank_lines(tmp_path):
    led = tmp_path / "api-cost.jsonl"
    led.write_text('{"stage":"select","cost_usd":1.0}\n\n')
    recs = cost_report.load_records(led)
    assert len(recs) == 1 and recs[0]["stage"] == "select"


def test_load_records_missing_file_is_empty(tmp_path):
    assert cost_report.load_records(tmp_path / "nope.jsonl") == []


def test_summarize_groups_by_stage_and_totals():
    recs = [
        {"stage": "select", "input_tokens": 10, "output_tokens": 5, "cost_usd": 1.0},
        {"stage": "select", "input_tokens": 20, "output_tokens": 5, "cost_usd": 2.0},
        {"stage": "metadata", "input_tokens": 4, "output_tokens": 2, "cost_usd": 0.5},
    ]
    s = cost_report.summarize(recs)
    assert s["total_cost"] == 3.5
    assert s["by_stage"]["select"]["calls"] == 2
    assert s["by_stage"]["select"]["input_tokens"] == 30
    assert s["by_stage"]["metadata"]["cost_usd"] == 0.5


def test_format_report_has_total_line():
    out = cost_report.format_report(cost_report.summarize(
        [{"stage": "select", "input_tokens": 1, "output_tokens": 1, "cost_usd": 2.0}]))
    assert "select" in out
    assert "TOTAL" in out
    assert "2.0000" in out
