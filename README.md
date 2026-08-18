# eval-harness

A small local harness for measuring how well an LLM does two different kinds
of task over 10-K filings:

- **Extraction** (5 fields, 50 cases) — figures with a right answer, scored
  on accuracy against a hand-authored answer key.
- **Analysis** (3 fields, 30 cases, ~90 claims) — judgments with no single
  right answer, scored on *grounding*: is every claim traceable to filing text?

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-...
```

## Adding a filing

1. Drop the 10-K (PDF or plain text) into `filings/`, named `{ticker}_{fy}.pdf`
   (or `.txt`), e.g. `filings/DDOG_2023.pdf`.
2. Add it to `config/filings.yaml`:
   ```yaml
   filings:
     - ticker: DDOG
       fy: 2023
       file: DDOG_2023.pdf
   ```
3. Keep all 10 filings in one industry — `config/fields.yaml`'s
   `operational_metrics` list is industry-specific and shared across the set.
   Edit that list before labeling if you change industries.

If a PDF's text extraction comes out under 500 characters per page on
average, `src/load.py` warns loudly (might need OCR before it's usable).

## Labeling

`labels/extraction_labels.csv` is the answer key: one row per
(filing, field) — 50 rows for a 10-filing, 5-field run. `expected_value` is a
JSON-encoded value matching the shape in `config/fields.yaml`:

| field | expected_value example |
|---|---|
| `capex` | `42.1` or `null` if not disclosed |
| `buybacks` | `0` if none occurred, `null` if not disclosed |
| `customer_concentration` | `[]` or `[{"customer_name_or_descriptor": "Customer A", "pct_of_revenue": 12.4}]` |
| `lease_and_offbs_obligations` | `{"operating_lease_liability": 55.0, "purchase_obligations": 10.2}` |
| `named_operational_metrics` | `{"net_revenue_retention": 118, "annual_recurring_revenue": 900.0, ...}` (one key per entry in `operational_metrics`, `null` for undisclosed ones) |

This is hand work and the only ground truth in the system.

Analysis fields have no answer key. Instead, `src/grade_analysis.py --emit`
builds a worksheet you fill in by hand after each run (see below).

## Running an eval

Extraction and analysis land in the same `runs/{timestamp}/` directory only
if you pass the same `--out` to both commands — pick a timestamp once and
reuse it:

```bash
RUN=runs/$(date +%Y%m%d_%H%M%S)

python -m src.run --fields extraction --prompt prompts/extraction_v1.txt \
    --model claude-sonnet-5 --out "$RUN"
python -m src.grade_extraction --run "$RUN"

python -m src.run --fields analysis --prompt prompts/analysis_v1.txt \
    --model claude-sonnet-5 --out "$RUN"
python -m src.grade_analysis --emit --run "$RUN"
# ... open runs/{timestamp}/analysis_worksheet.csv and fill in
#     claim_supported_by_citation, material, notes by hand ...
python -m src.grade_analysis --ingest --run "$RUN"

python -m src.report --run "$RUN"
```

Every `run.py` call is cached by hash of (filing, field, prompt text, model)
in `.cache/` (gitignored) — re-running is cheap and safe.

## Interpreting the metrics

**Extraction** (`extraction_scores.csv`):
- `CORRECT` / `WRONG` — numeric fields: within 1% of the label. List fields: no missing/invented entries and matched percentages within 1pp.
- `HALLUCINATED` — the label says "not disclosed" (`null`) and the model returned a value anyway, *or* the model invented a customer that isn't in the label's list. This is the most important failure mode to watch — it means the model is fabricating disclosures, not making an estimation error.
- `MISSED` — the label has a value and the model returned `null`, or the model's customer list is missing an entry the label has.
- `PARSE_ERROR` — the model's response wasn't valid JSON. `LOAD_ERROR` — the filing file was missing.
- `precision` / `recall` (customer_concentration rows only) — kept separate deliberately: a model that invents a customer and a model that misses one are different failure modes and averaging them together would hide that.

**Analysis** (`analysis_scores.csv`, from the hand-graded worksheet):
- `citation_validity_rate` — fraction of claims whose quoted text is actually found in the filing (this part is pre-checked automatically by `--emit` via substring search; you can override it if the model paraphrased instead of quoting).
- `support_rate` — fraction of claims where the citation, once found, actually supports the claim made. This is the headline analysis number, analogous to extraction accuracy.
- `materiality_rate` — fraction of claims you judged substantive rather than filler.
- `fabrication_count` — absolute count of claims with no valid citation. Reported as a count, not just a rate, because one fabricated claim in a document a human will act on is a real failure regardless of how many correct claims surround it.

**`report.md`** ties both halves together: run metadata, per-field breakdowns,
a side-by-side extraction-vs-analysis summary table (the headline result of
the project), a failure taxonomy grouped by verdict/pattern with example
cases, and a diff against the previous run in `runs/` if one exists.

## Iterating on prompts

Never edit a prompt file after a run has referenced it — `raw_outputs.jsonl`
records the exact prompt path used, and that reference has to stay valid.
Instead, copy to a new version (`prompts/extraction_v2.txt`) and re-run:

```bash
python -m src.run --fields extraction --prompt prompts/extraction_v2.txt \
    --model claude-sonnet-5 --out runs/$(date +%Y%m%d_%H%M%S)
```

`src/report.py` automatically diffs against the immediately preceding run
directory under `runs/`.

## Cost estimates

`src/report.py` only estimates cost for models listed in `config/pricing.yaml`
(gitignored rates you fill in yourself) — it reports "n/a" rather than guess
at pricing that may be stale.

## Layout

```
filings/        # gitignored -- 10-K PDFs/text, {ticker}_{fy}.ext
config/
  fields.yaml     # field definitions + industry operational metric names
  filings.yaml    # the 10 filings in the run set
  pricing.yaml    # optional $/Mtok rates for cost estimates
labels/
  extraction_labels.csv  # hand-authored answer key, 50 rows
prompts/
  extraction_v1.txt
  analysis_v1.txt
src/
  config.py             # yaml loaders
  load.py                # PDF/text loading, section split, chunking
  cache.py               # response cache
  run.py                 # calls the model over filings x fields
  grade_extraction.py    # scores against the answer key
  grade_analysis.py      # --emit worksheet, --ingest grounding metrics
  report.py              # aggregate report.md
runs/{timestamp}/
  raw_outputs.jsonl
  extraction_scores.csv
  analysis_worksheet.csv
  analysis_scores.csv
  report.md
```
