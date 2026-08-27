# Eval report: 20260819_104853

## Run metadata

- Run: `20260819_104853`
- Model(s): claude-sonnet-5
- Prompt file(s): prompts/extraction_v1.txt
- Filings: 6 (ADBE_2025, CRM_2026, MSFT_2026, NOW_2026, TEAM_2026, WDAY_2026)
- Total tokens: 3,806,542 in / 2,662 out
- Estimated cost: n/a (no config/pricing.yaml)


## Side-by-side summary

| | Extraction (accuracy) | Analysis (grounding) |
|---|---|---|
| Headline score | 77.1% | n/a (support rate) |
| Cases scored | 48 | n/a |
| Fabricated/hallucinated | 0 | n/a |


## Extraction

- Overall accuracy: 37/48 (77.1%)

Per-field accuracy:

- `buybacks`: 83.3%
- `capex`: 100.0%
- `lease_and_offbs_obligations`: 75.0%
- `named_operational_metrics`: 70.8%

Verdict distribution:

- CORRECT: 37
- WRONG: 8
- MISSED: 3

**Hallucination count: 0** (model returned a value where the label says nothing was disclosed, or invented a customer).


## Analysis

No analysis_scores.csv in this run (run `grade_analysis.py --emit` then `--ingest` after hand-grading).


## Failure taxonomy: extraction

- **buybacks / WRONG** (1 cases)
  - MSFT_2026: expected=22271.0 actual="{'value': 16719}"
- **lease_and_offbs_obligations / WRONG** (3 cases)
  - ADBE_2025 key=operating_lease_liability: expected=438.0 actual='485'
  - TEAM_2026 key=purchase_obligations: expected=4695.0 actual='3735.049'
  - WDAY_2026 key=purchase_obligations: expected=1566.0 actual='510'
- **named_operational_metrics / MISSED** (3 cases)
  - ADBE_2025 key=gross_margin_subscription: expected=91.15 actual=null
  - CRM_2026 key=gross_margin_subscription: expected=82.74 actual=null
  - WDAY_2026 key=gross_margin_subscription: expected=82.66 actual=null
- **named_operational_metrics / WRONG** (4 cases)
  - ADBE_2025 key=annual_recurring_revenue: expected=25200.0 actual='25.2'
  - ADBE_2025 key=remaining_performance_obligations: expected=22520.0 actual='22.52'
  - CRM_2026 key=remaining_performance_obligations: expected=72400.0 actual='72.4'


## Failure taxonomy: analysis

No analysis_worksheet.csv in this run.


## Comparison to previous run

No previous run to compare against.

