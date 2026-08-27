# Eval report: 20260827_173336

## Run metadata

- Run: `20260827_173336`
- Model(s): claude-sonnet-5
- Prompt file(s): prompts/extraction_v2.txt
- Filings: 6 (ADBE_2025, CRM_2026, MSFT_2026, NOW_2026, TEAM_2026, WDAY_2026)
- Total tokens: 3,840,112 in / 2,401 out
- Estimated cost: n/a (no config/pricing.yaml)


## Side-by-side summary

| | Extraction (accuracy) | Analysis (grounding) |
|---|---|---|
| Headline score | 97.9% | n/a (support rate) |
| Cases scored | 48 | n/a |
| Fabricated/hallucinated | 0 | n/a |


## Extraction

- Overall accuracy: 47/48 (97.9%)

Per-field accuracy:

- `buybacks`: 100.0%
- `capex`: 100.0%
- `lease_and_offbs_obligations`: 100.0%
- `named_operational_metrics`: 95.8%

Verdict distribution:

- CORRECT: 47
- MISSED: 1

**Hallucination count: 0** (model returned a value where the label says nothing was disclosed, or invented a customer).


## Analysis

No analysis_scores.csv in this run (run `grade_analysis.py --emit` then `--ingest` after hand-grading).


## Failure taxonomy: extraction

- **named_operational_metrics / MISSED** (1 cases)
  - CRM_2026 key=remaining_performance_obligations: expected=72400.0 actual=null


## Failure taxonomy: analysis

No analysis_worksheet.csv in this run.


## Comparison to previous run

Comparing against `20260819_104853`:

Extraction accuracy delta (current - previous):
- `buybacks`: +16.7%
- `capex`: +0.0%
- `lease_and_offbs_obligations`: +25.0%
- `named_operational_metrics`: +25.0%


