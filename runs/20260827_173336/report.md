# Eval report: 20260827_173336

## Run metadata

- Run: `20260827_173336`
- Model(s): claude-sonnet-5
- Prompt file(s): prompts/analysis_v1.txt, prompts/extraction_v2.txt
- Filings: 6 (ADBE_2025, CRM_2026, MSFT_2026, NOW_2026, TEAM_2026, WDAY_2026)
- Total tokens: 6,711,952 in / 17,018 out
- Estimated cost: n/a (no config/pricing.yaml)


## Side-by-side summary

| | Extraction (accuracy) | Analysis (grounding) |
|---|---|---|
| Headline score | 97.9% | 57.4% (support rate) |
| Cases scored | 48 | 54 |
| Fabricated/hallucinated | 0 | 0 |


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
| `business_model_risks` | 18 | 100.0% | 55.6% | 100.0% | 0 |
| `competitive_threats` | 18 | 100.0% | 61.1% | 88.9% | 0 |
| `profitability_quality` | 18 | 100.0% | 55.6% | 100.0% | 0 |

**Fabrication count (absolute): 0** across 54 claims.


## Failure taxonomy: extraction

- **named_operational_metrics / MISSED** (1 cases)
  - CRM_2026 key=remaining_performance_obligations: expected=72400.0 actual=null


## Failure taxonomy: analysis

- **business_model_risks / citation found but does not support claim** (8 claims)
  - MSFT_2026: "Microsoft faces intense and evolving competition across all of its markets—including from vertically-integrated platform" (notes: Claim text is far more alarmist than cited text without justification)
  - MSFT_2026: "Microsoft's business model, which centers on providing trusted cloud and software infrastructure to customers globally, " (notes: Claim is generalizing from a single incident)
  - NOW_2026: "Intensifying competition from both established enterprise software vendors and new AI-native entrants could erode Servic" (notes: Claim text is too embellished and does not talk about competitors responding faster to new opportunities)
- **competitive_threats / citation found but does not support claim** (7 claims)
  - ADBE_2025: "Adobe faces intensifying competition specifically from AI and cloud-native companies and third-party generative/agentic " (notes: Cited text does not say anything about Adobe's model usage being blocked)
  - ADBE_2025: "Adobe operates in a highly competitive, low-barrier-to-entry environment against a broad range of companies—including la" (notes: Not sure that low barrier to entry is factually correct in the claim. Cited text does not mention anything about OS and social media companies which the claim has made up)
  - MSFT_2026: "Vertically-integrated competitors that control both hardware and software (and related services/marketplaces) pose a str" (notes: Cited text does not mention PC operating systems)
- **profitability_quality / citation found but does not support claim** (8 claims)
  - ADBE_2025: "Stock-based compensation is a significant non-cash expense embedded across operating costs that inflates GAAP net income" (notes: citation has almost no text)
  - CRM_2026: "Reported operating income and net income are reduced by, but cash flow is not affected by, substantial non-cash stock-ba" (notes: citation has almost no text)
  - MSFT_2026: "Reported net income and EPS were materially inflated by large, volatile mark-to-market/equity-method gains on the OpenAI" (notes: Claim is not as balanced as the cited text - it only includes the gain scenario from the OpenAI investment)


## Comparison to previous run

Comparing against `20260819_104853`:

Extraction accuracy delta (current - previous):
- `buybacks`: +16.7%
- `capex`: +0.0%
- `lease_and_offbs_obligations`: +25.0%
- `named_operational_metrics`: +25.0%


