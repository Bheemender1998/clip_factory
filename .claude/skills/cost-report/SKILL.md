---
name: cost-report
description: Summarize clip_factory API spend from logs/api-cost.jsonl by stage. Use when the user says "cost report", "how much did clipping cost", "check API spend", or "/cost-report".
---

# cost-report

Summarize per-call API spend (select + metadata LLM calls) from the JSONL ledger.

## Steps

1. Run the report:
   ```bash
   python3 -m clipper.cost_report
   ```
2. Read the table: spend grouped by `stage` (select / metadata), with token counts and a TOTAL line.
3. If `logs/api-cost.jsonl` is missing, the report is empty — that means no LLM calls have run yet.
4. Relay the TOTAL and the per-stage breakdown to the user; flag if a single run looks unusually expensive.
