# Eval report: 20260828_161611

## Run metadata

- Run: `20260828_161611`
- Model(s): claude-sonnet-5
- Prompt file(s): prompts/analysis_v2.txt, prompts/extraction_v2.txt
- Filings: 6 (ADBE_2025, CRM_2026, MSFT_2026, NOW_2026, TEAM_2026, WDAY_2026)
- Total tokens: 6,719,098 in / 22,971 out
- Estimated cost: n/a (no config/pricing.yaml)


## Side-by-side summary

| | Extraction (accuracy) | Analysis (grounding) |
|---|---|---|
| Headline score | 97.9% | 77.8% (support rate) |
| Cases scored | 48 | 54 |
| Fabricated/hallucinated | 0 | 1 |


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

| Field | Claims | Citation validity | Support rate | Materiality | Fabrications |
|---|---|---|---|---|---|
| `business_model_risks` | 18 | 100.0% | 94.4% | 100.0% | 0 |
| `competitive_threats` | 18 | 100.0% | 88.9% | 100.0% | 0 |
| `profitability_quality` | 18 | 94.4% | 50.0% | 100.0% | 1 |

**Fabrication count (absolute): 1** across 54 claims.


## Failure taxonomy: extraction

- **named_operational_metrics / MISSED** (1 cases)
  - CRM_2026 key=remaining_performance_obligations: expected=72400.0 actual=null


## Failure taxonomy: analysis

- **business_model_risks / citation found but does not support claim** (1 claims)
  - ADBE_2025: "Evolving and potentially conflicting AI regulations across jurisdictions could force Adobe to make costly changes to its" (notes: Adds 'the AI-centric strategy the business model now depends on', the tone differs significantly from cited text)
- **competitive_threats / citation found but does not support claim** (2 claims)
  - ADBE_2025: "Adobe faces intensifying competition specifically from companies offering generative and agentic AI solutions across pro" (notes: If the claim names the Digital Media and Digital Experience segments, which the cited text does not, it should also extend to the Advertising segment since the cited text clearly indicates that it is affected)
  - NOW_2026: "ServiceNow faces direct competition from large, established enterprise application software vendors—Microsoft, Oracle, S" (notes: Cited text is incomplete)
- **profitability_quality / citation found but does not support claim** (8 claims)
  - CRM_2026: "Of the $1,017 million in gains on strategic investments, net that flowed into fiscal 2026 pretax income of $9,520 millio" (notes: Claim contains figures such as $1,017m gains and $9,520m pretax income that are not in the cited text)
  - CRM_2026: "Sales commissions and related costs to obtain revenue contracts are capitalized and expensed over four years rather than" (notes: The claim contains figures such as $2,811m and $2,197m that are not in the cited text)
  - MSFT_2026: "A significant portion of the year-over-year swing in GAAP net income and diluted EPS is attributable to non-operating, m" (notes: Cited text contains nothing about non-GAAP calculations)
- **profitability_quality / fabricated citation** (1 claims)
  - CRM_2026: "Stock-based compensation of roughly $3.5 billion for fiscal 2026 is embedded directly within cost of revenues and each o" (notes: The claim reformatted a table into prose without sufficient cited evidence)


## Comparison to previous run

Comparing against `20260827_173336`:

Extraction accuracy delta (current - previous):
- `buybacks`: +0.0%
- `capex`: +0.0%
- `lease_and_offbs_obligations`: +0.0%
- `named_operational_metrics`: +0.0%

Analysis support-rate delta (current - previous):
- `business_model_risks`: +38.8%
- `competitive_threats`: +27.8%
- `profitability_quality`: -5.6%

