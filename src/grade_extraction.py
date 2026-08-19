"""Score an extraction run against labels/extraction_labels.csv.

    python -m src.grade_extraction --run runs/{timestamp}

Writes {run}/extraction_scores.csv. Fails loudly (nonzero exit) if any case
present in the run has no corresponding hand-authored label
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.config import REPO_ROOT, extraction_field_by_id, load_fields_config

LABELS_PATH = REPO_ROOT / "labels" / "extraction_labels.csv"
NUMERIC_TOLERANCE = 0.01  # 1%
PCT_TOLERANCE_POINTS = 1.0  # 1 percentage point, for customer pct_of_revenue


def latest_run_dir() -> Path:
    runs = sorted(p for p in (REPO_ROOT / "runs").iterdir() if p.is_dir())
    if not runs:
        raise FileNotFoundError("no run directories under runs/")
    return runs[-1]


def load_labels() -> dict[tuple[str, str], object]:
    if not LABELS_PATH.exists():
        raise FileNotFoundError(f"missing {LABELS_PATH}")
    df = pd.read_csv(LABELS_PATH)
    labels = {}
    for _, row in df.iterrows():
        expected = None if pd.isna(row["expected_value"]) else json.loads(row["expected_value"])
        labels[(row["filing"], row["field_id"])] = expected
    return labels


def load_run_cases(run_dir: Path) -> dict[tuple[str, str], dict]:
    """Pick one record per (filing, field): prefer a chunk that actually
    parsed to a non-null value (i.e. found something), else chunk 0."""
    path = run_dir / "raw_outputs.jsonl"
    by_case: dict[tuple[str, str], list[dict]] = {}
    with open(path) as f:
        for line in f:
            record = json.loads(line)
            key = (record["filing"], record["field"])
            by_case.setdefault(key, []).append(record)

    chosen = {}
    for key, records in by_case.items():
        records.sort(key=lambda r: r["chunk_index"])
        found = [r for r in records if r["parse_status"] == "OK" and r["parsed_value"] is not None]
        chosen[key] = found[0] if found else records[0]
    return chosen


def _unwrap_numeric(actual):
    """The model sometimes wraps a bare numeric answer in a single-key JSON
    object (e.g. {"value": 179}) instead of the plain number the prompt asks
    for -- the wrapper key name varies and isn't predictable. Unwrap one
    level rather than scoring it as a shape mismatch."""
    if isinstance(actual, dict) and len(actual) == 1:
        return next(iter(actual.values()))
    return actual


def numeric_verdict(expected, actual):
    """Returns (verdict, error_magnitude) for a single numeric field/key."""
    actual = _unwrap_numeric(actual)
    if expected is None:
        if actual is None:
            return "CORRECT", None
        return "HALLUCINATED", None
    if actual is None:
        return "MISSED", None
    if not isinstance(actual, (int, float)):
        return "PARSE_ERROR", None
    if expected == 0:
        return ("CORRECT" if actual == 0 else "WRONG"), (actual - expected)
    rel_err = (actual - expected) / expected
    verdict = "CORRECT" if abs(rel_err) <= NUMERIC_TOLERANCE else "WRONG"
    return verdict, rel_err


def score_number(expected, actual) -> list[dict]:
    verdict, err = numeric_verdict(expected, actual)
    return [{"key": "", "expected": expected, "actual": actual, "verdict": verdict, "error_magnitude": err}]


def score_dict_numeric(expected, actual, keys: list[str]) -> list[dict]:
    expected = expected or {}
    actual = actual or {}
    all_keys = keys if keys else sorted(set(expected) | set(actual))
    rows = []
    for key in all_keys:
        verdict, err = numeric_verdict(expected.get(key), actual.get(key))
        rows.append(
            {"key": key, "expected": expected.get(key), "actual": actual.get(key), "verdict": verdict, "error_magnitude": err}
        )
    return rows


def _norm_name(name: str) -> str:
    return name.strip().lower()


def score_customer_list(expected: list | None, actual: list | None) -> list[dict]:
    expected = expected or []
    actual = actual or []

    expected_by_name = {_norm_name(c["customer_name_or_descriptor"]): c["pct_of_revenue"] for c in expected}
    actual_by_name = {_norm_name(c["customer_name_or_descriptor"]): c["pct_of_revenue"] for c in actual}

    expected_names = set(expected_by_name)
    actual_names = set(actual_by_name)
    matched = expected_names & actual_names
    missed = expected_names - actual_names
    hallucinated = actual_names - expected_names

    pct_mismatches = [
        name for name in matched
        if abs(actual_by_name[name] - expected_by_name[name]) > PCT_TOLERANCE_POINTS
    ]

    precision = (len(matched) / len(actual_names)) if actual_names else (1.0 if not expected_names else 0.0)
    recall = (len(matched) / len(expected_names)) if expected_names else (1.0 if not actual_names else 0.0)

    if not hallucinated and not missed and not pct_mismatches:
        verdict = "CORRECT"
    elif hallucinated and not missed:
        verdict = "HALLUCINATED"
    elif missed and not hallucinated:
        verdict = "MISSED"
    else:
        verdict = "WRONG"

    return [
        {
            "key": "",
            "expected": json.dumps(expected),
            "actual": json.dumps(actual),
            "verdict": verdict,
            "error_magnitude": None,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "hallucinated_count": len(hallucinated),
            "missed_count": len(missed),
            "notes": f"pct_mismatches={sorted(pct_mismatches)}" if pct_mismatches else "",
        }
    ]


def grade(run_dir: Path) -> pd.DataFrame:
    fields_cfg = load_fields_config()
    labels = load_labels()
    run_cases = load_run_cases(run_dir)

    # A run directory may hold both extraction and analysis records (they're
    # meant to share one runs/{timestamp}/ dir) -- only extraction cases need
    # an answer-key label.
    extraction_field_ids = {f["id"] for f in fields_cfg.get("extraction_fields", [])}
    run_cases = {k: v for k, v in run_cases.items() if k[1] in extraction_field_ids}

    missing = sorted(set(run_cases) - set(labels))
    if missing:
        formatted = "\n".join(f"  - filing={f} field={fld}" for f, fld in missing)
        raise SystemExit(
            f"Missing labels for {len(missing)} case(s) present in the run. "
            f"Label labels/extraction_labels.csv before grading:\n{formatted}"
        )

    rows = []
    for (fid, field_id), expected in labels.items():
        if (fid, field_id) not in run_cases:
            continue  # label exists for a case not in this run; skip rather than fabricate a row
        record = run_cases[(fid, field_id)]
        field = extraction_field_by_id(fields_cfg, field_id)
        actual = record["parsed_value"]

        if record["parse_status"] != "OK":
            rows.append(
                {
                    "filing": fid, "field": field_id, "key": "",
                    "expected": json.dumps(expected), "actual": None,
                    "verdict": record["parse_status"], "error_magnitude": None,
                    "precision": None, "recall": None,
                    "hallucinated_count": None, "missed_count": None,
                    "notes": record.get("error") or "",
                }
            )
            continue

        if field["value_type"] == "number":
            sub_rows = score_number(expected, actual)
        elif field["value_type"] == "dict_numeric":
            sub_rows = score_dict_numeric(expected, actual, field.get("keys") or [])
        elif field["value_type"] == "customer_list":
            sub_rows = score_customer_list(expected, actual)
        else:
            raise ValueError(f"unknown value_type for field {field_id}")

        for sub in sub_rows:
            sub.setdefault("precision", None)
            sub.setdefault("recall", None)
            sub.setdefault("hallucinated_count", None)
            sub.setdefault("missed_count", None)
            sub.setdefault("notes", "")
            rows.append({"filing": fid, "field": field_id, **sub})

    return pd.DataFrame(rows, columns=[
        "filing", "field", "key", "expected", "actual", "verdict", "error_magnitude",
        "precision", "recall", "hallucinated_count", "missed_count", "notes",
    ])


def main() -> None:
    parser = argparse.ArgumentParser(description="Grade an extraction run against the answer key.")
    parser.add_argument("--run", default=None, help="Run directory (default: latest under runs/).")
    args = parser.parse_args()

    run_dir = Path(args.run) if args.run else latest_run_dir()
    df = grade(run_dir)

    out_path = run_dir / "extraction_scores.csv"
    df.to_csv(out_path, index=False)

    total = len(df)
    correct = (df["verdict"] == "CORRECT").sum()
    hallucinated = (df["verdict"] == "HALLUCINATED").sum() + df["hallucinated_count"].fillna(0).astype(int).sum()
    parse_errors = df["verdict"].isin(["PARSE_ERROR", "LOAD_ERROR"]).sum()
    accuracy = correct / total if total else float("nan")

    print(
        f"extraction: {correct}/{total} correct ({accuracy:.1%}), "
        f"{hallucinated} hallucinated, {parse_errors} parse/load errors -> {out_path}"
    )


if __name__ == "__main__":
    main()
