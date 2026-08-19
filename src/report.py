"""Aggregate a run's scores into runs/{timestamp}/report.md.

    python -m src.report --run runs/{timestamp}

Reads whichever of extraction_scores.csv / analysis_scores.csv /
analysis_worksheet.csv exist in the run directory -- a run that only covers
one half of the eval still produces a (partial) report.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import yaml

from src.config import REPO_ROOT

PRICING_PATH = REPO_ROOT / "config" / "pricing.yaml"
EXAMPLES_PER_PATTERN = 3


def latest_run_dir(exclude: Path | None = None) -> Path | None:
    runs = sorted(p for p in (REPO_ROOT / "runs").iterdir() if p.is_dir())
    if exclude is not None:
        runs = [r for r in runs if r.resolve() != exclude.resolve()]
    return runs[-1] if runs else None


def find_previous_run(run_dir: Path) -> Path | None:
    runs = sorted(p for p in (REPO_ROOT / "runs").iterdir() if p.is_dir())
    names = [p.name for p in runs]
    if run_dir.name not in names:
        return None
    idx = names.index(run_dir.name)
    return runs[idx - 1] if idx > 0 else None


def load_raw_outputs(run_dir: Path) -> pd.DataFrame:
    path = run_dir / "raw_outputs.jsonl"
    if not path.exists():
        return pd.DataFrame()
    records = [json.loads(line) for line in open(path)]
    return pd.DataFrame(records)


def load_csv_if_exists(path: Path) -> pd.DataFrame | None:
    return pd.read_csv(path) if path.exists() else None


def estimate_cost(raw_df: pd.DataFrame) -> str:
    if raw_df.empty:
        return "n/a"
    with open(PRICING_PATH) as f:
        pricing = (yaml.safe_load(f) or {}).get("models", {})

    total = 0.0
    priced_any = False
    for model, group in raw_df.groupby("model"):
        if model not in pricing:
            continue
        priced_any = True
        rates = pricing[model]
        total += group["input_tokens"].sum() / 1e6 * rates["input_per_mtok"]
        total += group["output_tokens"].sum() / 1e6 * rates["output_per_mtok"]

    if not priced_any:
        return "n/a (add model rates to config/pricing.yaml)"
    return f"${total:.2f}"


def render_metadata(run_dir: Path, raw_df: pd.DataFrame) -> str:
    if raw_df.empty:
        return "No raw_outputs.jsonl found in this run directory.\n"

    models = sorted(raw_df["model"].dropna().unique())
    prompts = sorted(raw_df["prompt_file"].dropna().unique())
    filings = sorted(raw_df["filing"].dropna().unique())
    total_in = int(raw_df["input_tokens"].fillna(0).sum())
    total_out = int(raw_df["output_tokens"].fillna(0).sum())

    lines = [
        f"- Run: `{run_dir.name}`",
        f"- Model(s): {', '.join(models)}",
        f"- Prompt file(s): {', '.join(prompts)}",
        f"- Filings: {len(filings)} ({', '.join(filings)})",
        f"- Total tokens: {total_in:,} in / {total_out:,} out",
        f"- Estimated cost: {estimate_cost(raw_df)}",
    ]
    return "\n".join(lines) + "\n"


def render_extraction_section(scores: pd.DataFrame | None) -> tuple[str, dict]:
    if scores is None or scores.empty:
        return "No extraction_scores.csv in this run.\n", {}

    total = len(scores)
    correct = (scores["verdict"] == "CORRECT").sum()
    overall_accuracy = correct / total if total else float("nan")

    per_field = scores.groupby("field")["verdict"].apply(lambda s: (s == "CORRECT").mean())
    verdict_counts = scores["verdict"].value_counts()

    hallucination_from_numeric = ((scores["verdict"] == "HALLUCINATED") & scores["hallucinated_count"].isna()).sum()
    hallucination_from_lists = scores["hallucinated_count"].fillna(0).sum()
    total_hallucinations = int(hallucination_from_numeric + hallucination_from_lists)

    lines = [f"- Overall accuracy: {correct}/{total} ({overall_accuracy:.1%})", "", "Per-field accuracy:", ""]
    for field, acc in per_field.items():
        lines.append(f"- `{field}`: {acc:.1%}")
    lines += ["", "Verdict distribution:", ""]
    for verdict, count in verdict_counts.items():
        lines.append(f"- {verdict}: {count}")
    lines += ["", f"**Hallucination count: {total_hallucinations}** (model returned a value where the label says nothing was disclosed, or invented a customer)."]

    summary = {"accuracy": overall_accuracy, "hallucinations": total_hallucinations, "n": total}
    return "\n".join(lines) + "\n", summary


def render_analysis_section(scores: pd.DataFrame | None) -> tuple[str, dict]:
    if scores is None or scores.empty:
        return "No analysis_scores.csv in this run (run `grade_analysis.py --emit` then `--ingest` after hand-grading).\n", {}

    lines = ["| Field | Claims | Citation validity | Support rate | Materiality | Fabrications |",
             "|---|---|---|---|---|---|"]
    for _, row in scores.iterrows():
        lines.append(
            f"| `{row['field']}` | {row['num_claims']} | {row['citation_validity_rate']:.1%} | "
            f"{row['support_rate']:.1%} | {row['materiality_rate']:.1%} | {row['fabrication_count']} |"
        )

    total_claims = scores["num_claims"].sum()
    total_fabrications = scores["fabrication_count"].sum()
    weighted_validity = (scores["citation_validity_rate"] * scores["num_claims"]).sum() / total_claims if total_claims else float("nan")
    weighted_support = (scores["support_rate"] * scores["num_claims"]).sum() / total_claims if total_claims else float("nan")

    lines += ["", f"**Fabrication count (absolute): {int(total_fabrications)}** across {int(total_claims)} claims."]

    summary = {"citation_validity": weighted_validity, "support_rate": weighted_support, "fabrications": int(total_fabrications), "n": int(total_claims)}
    return "\n".join(lines) + "\n", summary


def render_side_by_side(ext_summary: dict, ana_summary: dict) -> str:
    ext_acc = f"{ext_summary['accuracy']:.1%}" if ext_summary else "n/a"
    ana_grounding = f"{ana_summary['support_rate']:.1%}" if ana_summary else "n/a"
    ext_fail = ext_summary.get("hallucinations", "n/a")
    ana_fail = ana_summary.get("fabrications", "n/a")
    ext_n = ext_summary.get("n", "n/a")
    ana_n = ana_summary.get("n", "n/a")

    return (
        "| | Extraction (accuracy) | Analysis (grounding) |\n"
        "|---|---|---|\n"
        f"| Headline score | {ext_acc} | {ana_grounding} (support rate) |\n"
        f"| Cases scored | {ext_n} | {ana_n} |\n"
        f"| Fabricated/hallucinated | {ext_fail} | {ana_fail} |\n"
    )


def _clean(value) -> str:
    """CSV round-trips empty strings as NaN, and NaN is truthy in Python --
    without this, blank key/notes cells render as the literal text "nan"."""
    return "" if pd.isna(value) else str(value)


def _fmt_value(value) -> str:
    """Like _clean, but for expected/actual columns where a blank cell means
    an actual null/missing value worth calling out, not nothing to say."""
    return "null" if pd.isna(value) else repr(value)


def render_extraction_taxonomy(scores: pd.DataFrame | None) -> str:
    if scores is None or scores.empty:
        return "No extraction failures to group (no extraction_scores.csv).\n"

    failures = scores[scores["verdict"] != "CORRECT"]
    if failures.empty:
        return "No extraction failures.\n"

    lines = []
    for (field, verdict), group in failures.groupby(["field", "verdict"]):
        lines.append(f"- **{field} / {verdict}** ({len(group)} cases)")
        for _, row in group.head(EXAMPLES_PER_PATTERN).iterrows():
            key_str = _clean(row.get("key"))
            key = f" key={key_str}" if key_str else ""
            notes = _clean(row.get("notes"))
            lines.append(f"  - {row['filing']}{key}: expected={_fmt_value(row['expected'])} actual={_fmt_value(row['actual'])} {notes}".rstrip())
    return "\n".join(lines) + "\n"


def render_analysis_taxonomy(worksheet: pd.DataFrame | None) -> str:
    if worksheet is None or worksheet.empty:
        return "No analysis_worksheet.csv in this run.\n"

    def to_bool(v):
        if isinstance(v, bool):
            return v
        s = str(v).strip().lower()
        return s in {"true", "t", "1", "yes"}

    claims = worksheet[worksheet["claim_text"].fillna("").astype(str).str.len() > 0].copy()
    if claims.empty:
        return "No graded claims in the worksheet yet.\n"

    claims["citation_found_in_filing"] = claims["citation_found_in_filing"].map(to_bool)
    claims["claim_supported_by_citation"] = claims["claim_supported_by_citation"].map(to_bool)

    def pattern(row):
        if not row["citation_found_in_filing"]:
            return "fabricated citation"
        if not row["claim_supported_by_citation"]:
            return "citation found but does not support claim"
        return None

    claims["pattern"] = claims.apply(pattern, axis=1)
    failures = claims[claims["pattern"].notna()]
    if failures.empty:
        return "No analysis grounding failures.\n"

    lines = []
    for (field, pat), group in failures.groupby(["field", "pattern"]):
        lines.append(f"- **{field} / {pat}** ({len(group)} claims)")
        for _, row in group.head(EXAMPLES_PER_PATTERN).iterrows():
            notes = _clean(row.get("notes"))
            lines.append(f"  - {row['filing']}: \"{row['claim_text'][:120]}\" (notes: {notes})".rstrip())
    return "\n".join(lines) + "\n"


def render_comparison(run_dir: Path, ext_scores: pd.DataFrame | None, ana_scores: pd.DataFrame | None) -> str:
    prev_dir = find_previous_run(run_dir)
    if prev_dir is None:
        return "No previous run to compare against.\n"

    lines = [f"Comparing against `{prev_dir.name}`:", ""]

    prev_ext = load_csv_if_exists(prev_dir / "extraction_scores.csv")
    if ext_scores is not None and prev_ext is not None:
        cur = ext_scores.groupby("field")["verdict"].apply(lambda s: (s == "CORRECT").mean())
        prev = prev_ext.groupby("field")["verdict"].apply(lambda s: (s == "CORRECT").mean())
        lines.append("Extraction accuracy delta (current - previous):")
        for field in sorted(set(cur.index) | set(prev.index)):
            delta = cur.get(field, float("nan")) - prev.get(field, float("nan"))
            lines.append(f"- `{field}`: {delta:+.1%}")
        lines.append("")

    prev_ana = load_csv_if_exists(prev_dir / "analysis_scores.csv")
    if ana_scores is not None and prev_ana is not None:
        cur = ana_scores.set_index("field")["support_rate"]
        prev = prev_ana.set_index("field")["support_rate"]
        lines.append("Analysis support-rate delta (current - previous):")
        for field in sorted(set(cur.index) | set(prev.index)):
            delta = cur.get(field, float("nan")) - prev.get(field, float("nan"))
            lines.append(f"- `{field}`: {delta:+.1%}")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build report.md for a run.")
    parser.add_argument("--run", default=None, help="Run directory (default: latest under runs/).")
    args = parser.parse_args()

    run_dir = Path(args.run) if args.run else latest_run_dir()
    if run_dir is None:
        raise SystemExit("no run directories under runs/")

    raw_df = load_raw_outputs(run_dir)
    ext_scores = load_csv_if_exists(run_dir / "extraction_scores.csv")
    ana_scores = load_csv_if_exists(run_dir / "analysis_scores.csv")
    ana_worksheet = load_csv_if_exists(run_dir / "analysis_worksheet.csv")

    ext_section, ext_summary = render_extraction_section(ext_scores)
    ana_section, ana_summary = render_analysis_section(ana_scores)

    report = f"""# Eval report: {run_dir.name}

## Run metadata

{render_metadata(run_dir, raw_df)}

## Side-by-side summary

{render_side_by_side(ext_summary, ana_summary)}

## Extraction

{ext_section}

## Analysis

{ana_section}

## Failure taxonomy: extraction

{render_extraction_taxonomy(ext_scores)}

## Failure taxonomy: analysis

{render_analysis_taxonomy(ana_worksheet)}

## Comparison to previous run

{render_comparison(run_dir, ext_scores, ana_scores)}
"""

    out_path = run_dir / "report.md"
    out_path.write_text(report)

    ext_acc = f"{ext_summary['accuracy']:.1%}" if ext_summary else "n/a"
    ana_support = f"{ana_summary['support_rate']:.1%}" if ana_summary else "n/a"
    print(f"report: extraction accuracy {ext_acc}, analysis support rate {ana_support} -> {out_path}")


if __name__ == "__main__":
    main()
