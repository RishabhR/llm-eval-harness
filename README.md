# eval-harness

Measuring how well an LLM does two different kinds of work over SEC 10-K
filings — and whether the difference between them can be verified automatically.

- **Extraction** — pulling disclosed figures. Has a right answer, scored on
  accuracy against a hand-authored key.
- **Analysis** — writing judgments about the business. Has no single right
  answer, so it is scored on *grounding*: does every claim trace to filing text?

---

## Results

Six software/SaaS 10-Ks, one model (Claude Sonnet 5), three runs, two prompt
versions per task. Every figure below was graded by hand against the filings.

| | Extraction | Analysis |
|---|---:|---:|
| Best score | **97.9%** accuracy | **77.8%** of claims supported by their citation |
| Fabricated / hallucinated | **0** | 1 |
| Citation validity | — | 98.1% |
| Scored units | 48 values across 24 extractions | 54 claims across 18 responses |

### The finding

**Extraction is close to shippable with spot-checks. Analysis is not — and the
reason is invisible to the check you would automate.**

Across both analysis runs a human reader judged 35 claims unsupported.
**34 of those 35 had a citation that passed the automated verification.**

The model almost never invents a quote — citation validity ran 98–100%. What it
does instead is quote real filing text and then claim more than that text
establishes: adding a competitor the passage never names, a causal mechanism it
never states, a consequence it never draws. A pipeline that verified citations
existed would have reported near-perfect grounding and caught essentially none
of the real failures.

That asymmetry is the case for treating analysis output as **evidence surfaced
for a human analyst**, not as a conclusion to be consumed directly — and it is
not something the aggregate score alone would have told you.

### What prompt iteration did

| | v1 | v2 |
|---|---:|---:|
| Extraction accuracy | 77.1% | **97.9%** |
| Analysis support rate | 57.4% | **77.8%** |

Extraction's v1 failures were mechanical and diagnosable: figures returned in
billions where millions were asked for, values wrapped in a JSON object instead
of returned bare. Stating the unit conversion and the output shape explicitly
fixed nearly all of them.

Analysis v1 failed differently. Its worst claims were its *top-ranked* ones —
support by claim slot ran 50% / 44% / 78%, because the model's most ambitious
claims outran what a single passage could carry. v2 inverted the order (select
the passage, then write the claim it licenses) and required every element of a
claim to appear in the quote. Two of three fields improved sharply
(`business_model_risks` 55.6% → 94.4%, `competitive_threats` 61.1% → 88.9%).

The third did not. `profitability_quality` went 55.6% → 50.0%: v2 fixed its
habit of citing a bare table row for an interpretive claim, but replaced it with
claims that attach figures the quote does not contain. Scoping applied to prose
and not to numbers.

### The answer key was the hardest part

Grading the model surfaced errors in the ground truth. Every label value that a
model answer disagreed with was re-checked line-by-line against the filing text;
**five of those turned out to be wrong in the key, not in the answer** —
including one that made a correct extraction register as the run's only
hallucination, and one that had been imported from a previous run's model output
rather than read from the filing. Both runs were re-scored against the corrected
key, which is what moved extraction from 89.6% to 97.9%.

The harness therefore refuses to grade a case with no label rather than scoring
a partial set, and every corrected label records its filing source. The
labelling, not the plumbing, is where the accuracy of a project like this
actually lives.

### What would need to be true to trust this further

- **Six filings, one industry, one model.** Enough to see a pattern, not enough
  to size it.
- **Prompts were tuned on the same filings they are scored on.** There is no
  held-out set, so both v2 improvements are optimistic.
- **Analysis grading is one reader, single-pass.** Support and materiality are
  judgment calls; the first pass drifted enough that
  [`labels/analysis_rubric.md`](labels/analysis_rubric.md) exists to pin the
  threshold, and re-grading against it moved the headline by 26 points.
- **Grader provenance is mixed in the final run** — 37 of 54 claims were
  pre-graded mechanically against the rubric and then reviewed (94.6% upheld);
  the earlier run was hand-graded throughout.
- **Materiality returned 100% in every run**, so that metric produced no signal
  and may not be calibrated.

---

## How it works

Everything is CLI and flat files — CSV and JSONL, no database, no web UI.
Filings are placed on disk by hand; nothing is fetched from EDGAR. Ground truth
is authored by a human, never generated, since grading a model against a model
would defeat the point.

### Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-...
```

`pypdf` is pinned deliberately: extracted filing text is part of the response
cache key, so a version bump silently orphans `.cache/` and makes a re-run cost
a full set of API calls.

### The run set

Six software/SaaS filings, listed in `config/filings.yaml`:

| Ticker | FY | | Ticker | FY |
|---|---|---|---|---|
| ADBE | 2025 | | NOW | 2026 |
| CRM | 2026 | | TEAM | 2026 |
| MSFT | 2026 | | WDAY | 2026 |

Single-industry by design — `named_operational_metrics` is industry-specific and
shared across the set.

**Extraction fields** (4) — `capex`, `buybacks`, `lease_and_offbs_obligations`
(operating lease liability + purchase obligations), `named_operational_metrics`
(net revenue retention, ARR, subscription gross margin, RPO).

**Analysis fields** (3) — `business_model_risks`, `competitive_threats`,
`profitability_quality`.

The dict-valued fields are scored per key, so 24 extractions produce 48 scored
values.

### Adding a filing

1. Drop the 10-K (PDF or plain text) into `filings/`, named `{ticker}_{fy}.pdf`
   (or `.txt`) — e.g. `filings/ADBE_2025.pdf`. Filings are gitignored: they are
   large, and freely available from EDGAR.
2. Add it to `config/filings.yaml`:
   ```yaml
   filings:
     - ticker: ADBE
       fy: 2025
       file: ADBE_2025.pdf
   ```
3. Keep the set within one industry, and edit `operational_metrics` in
   `config/fields.yaml` before labelling if you change industries.

If PDF text extraction averages under 500 characters per page, `src/load.py`
warns loudly — the filing is probably scanned and needs OCR first.

### Labelling

`labels/extraction_labels.csv` is the answer key: one row per (filing, field),
so **24 rows** for the current 6-filing, 4-field set. `expected_value` is
JSON-encoded and must match the shape declared in `config/fields.yaml`:

| field | `expected_value` example |
|---|---|
| `capex` | `42.1`, or `null` if not disclosed |
| `buybacks` | `0` if none occurred, `null` if not disclosed |
| `lease_and_offbs_obligations` | `{"operating_lease_liability": 55.0, "purchase_obligations": 10.2}` |
| `named_operational_metrics` | `{"net_revenue_retention": 118, "annual_recurring_revenue": 900.0, ...}` — one key per entry in `operational_metrics`, `null` where undisclosed |

Use `null` for "the filing does not disclose this". That distinction is what
lets the grader separate an honest omission from an invented figure.

> **Editing tip:** open these CSVs in a spreadsheet application and export,
> rather than editing them in a text editor. Notes and labels contain commas,
> and unquoted commas have corrupted this file more than once.

Analysis fields have no answer key. `src/grade_analysis.py --emit` builds a
worksheet you fill in by hand, graded against
[`labels/analysis_rubric.md`](labels/analysis_rubric.md).

### Running an eval

Both halves share one run directory — pass the same `--out` to each, so
`report.py` can render the side-by-side table:

```bash
RUN=runs/$(date +%Y%m%d_%H%M%S)

python -m src.run --fields extraction --prompt prompts/extraction_v2.txt \
    --model claude-sonnet-5 --out "$RUN"
python -m src.grade_extraction --run "$RUN"

python -m src.run --fields analysis --prompt prompts/analysis_v2.txt \
    --model claude-sonnet-5 --out "$RUN"
python -m src.grade_analysis --emit --run "$RUN"
# ... fill in claim_supported_by_citation, material and notes by hand ...
python -m src.grade_analysis --ingest --run "$RUN"

python -m src.report --run "$RUN"
```

Each call is cached by hash of (filing, field, prompt text, model) in `.cache/`,
so re-running is free. Responses that fail to parse are deliberately **not**
cached — a truncated answer is an infrastructure artifact, and caching it would
make the failure permanent.

A full run is roughly 6.7M input tokens (~$15–20 at list prices); the three runs
here cost about 10.5M tokens of live calls.

### Interpreting the metrics

**Extraction** (`extraction_scores.csv`):

| Verdict | Meaning |
|---|---|
| `CORRECT` | Numeric value within 1% of the label |
| `WRONG` | Outside tolerance |
| `HALLUCINATED` | The label says "not disclosed" and the model returned a value anyway. The most important failure mode — it means fabricating a disclosure, not misreading one. |
| `MISSED` | The label has a value and the model returned `null` |
| `PARSE_ERROR` / `LOAD_ERROR` | Response wasn't valid JSON / filing file missing |

Numbers wrapped in a single-key object (`{"value": 179}`) are unwrapped before
comparison — the model does this intermittently, and it is a formatting failure
rather than an extraction one.

**Analysis** (`analysis_scores.csv`, from the hand-graded worksheet):

- `citation_validity_rate` — fraction of claims whose quoted text is actually
  present in the filing. Pre-checked automatically, tolerant of case, PDF
  line-break hyphenation, typographic quotes, and ellipsis-joined passages
  (each fragment must match on its own). **Passing this says only that the quote
  is real** — on this run set it passed on 34 of the 35 claims a human judged
  unsupported.
- `support_rate` — fraction of claims the citation actually supports. The
  headline analysis number, analogous to extraction accuracy, and the one that
  requires a human.
- `materiality_rate` — fraction judged substantive rather than filler.
- `fabrication_count` — absolute count of claims with no valid citation.
  Reported as a count, never only a rate: one fabricated claim in a document a
  human will act on is a product-level failure regardless of the denominator.

**`report.md`** ties both halves together — run metadata, per-field breakdowns,
the side-by-side summary, a failure taxonomy with example cases, and a diff
against the previous run.

### Iterating on prompts

Never edit a prompt after a run references it — `raw_outputs.jsonl` records the
path used, and that reference has to stay valid. Copy to a new version instead
(`prompts/analysis_v3.txt`) and re-run; `report.py` diffs automatically against
the preceding run directory.

## Layout

```
filings/                     # gitignored -- 10-K PDFs/text, {ticker}_{fy}.ext
config/
  fields.yaml                # field definitions, per-field prompt guidance,
                             #   industry operational metric names
  filings.yaml               # the filings in the run set
labels/
  extraction_labels.csv      # hand-authored answer key, one row per case
  analysis_rubric.md         # written grading rule for the analysis worksheet
prompts/
  extraction_v1.txt          # versioned by filename, never edited in place
  extraction_v2.txt
  analysis_v1.txt
  analysis_v2.txt
src/
  config.py                  # yaml loaders
  load.py                    # PDF/text loading, section split, chunking
  cache.py                   # response cache
  run.py                     # calls the model over filings x fields
  grade_extraction.py        # scores against the answer key
  grade_analysis.py          # --emit worksheet, --ingest grounding metrics
  report.py                  # aggregate report.md
runs/{timestamp}/
  raw_outputs.jsonl          # one line per case: response, parse status,
                             #   tokens, latency, stop_reason
  extraction_scores.csv
  analysis_worksheet.csv     # the hand-graded artifact
  analysis_scores.csv
  report.md
```
