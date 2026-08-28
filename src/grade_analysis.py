"""Build and ingest the manual grading worksheet for analysis-field runs.

    python -m src.grade_analysis --emit --run runs/{timestamp}
    # ... operator fills in claim_supported_by_citation, material, notes ...
    python -m src.grade_analysis --ingest --run runs/{timestamp}

--emit splits each model response into individual claims (grading happens per
claim, not per response) and pre-populates citation_found_in_filing by exact
substring search -- the only part of grading that is mechanical. Everything
else is the operator's judgment call.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

from src.config import REPO_ROOT, load_fields_config, load_filings_config
from src.load import load_filing

WORKSHEET_COLUMNS = [
    "filing", "field", "claim_index", "claim_text", "cited_text",
    "citation_found_in_filing", "claim_supported_by_citation", "material", "notes",
]


def latest_run_dir() -> Path:
    runs = sorted(p for p in (REPO_ROOT / "runs").iterdir() if p.is_dir())
    if not runs:
        raise FileNotFoundError("no run directories under runs/")
    return runs[-1]


def load_run_cases(run_dir: Path) -> dict[tuple[str, str], dict]:
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


def _normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _normalize_for_match(s: str) -> str:
    """Normalize both sides of the citation substring check.

    The check answers "does this text appear in the filing", and two
    artifacts made it answer "no" for citations that were in fact faithful:

    - Quoting mid-sentence capitalizes the first letter ("we expect" quoted
      as "We expect"), which is ordinary practice, not a fabrication.
    - PDF extraction breaks words across lines as "non- GAAP"; a model that
      writes "non-GAAP" is reproducing the filing correctly.

    Both are semantically neutral and applied to filing and citation alike,
    so this cannot turn an invented citation into a match -- it only stops
    fabrication_count from counting real quotes.
    """
    s = _normalize_ws(s).lower()
    return re.sub(r"(\w)-\s+(\w)", r"\1-\2", s)


def _filing_text_cache(filings: list[dict]) -> dict[str, str]:
    from src.config import filing_id

    cache = {}
    for entry in filings:
        fid = filing_id(entry["ticker"], entry["fy"])
        try:
            cache[fid] = load_filing(entry["ticker"], entry["fy"])
        except FileNotFoundError:
            cache[fid] = ""
    return cache


def emit(run_dir: Path) -> Path:
    fields_cfg = load_fields_config()
    filings = load_filings_config()
    run_cases = load_run_cases(run_dir)
    texts = _filing_text_cache(filings)

    analysis_field_ids = {f["id"] for f in fields_cfg.get("analysis_fields", [])}
    rows = []
    num_analysis_cases = 0
    for (fid, field_id), record in sorted(run_cases.items()):
        if field_id not in analysis_field_ids:
            continue  # this run dir may also hold extraction cases sharing the directory
        num_analysis_cases += 1

        if record["parse_status"] != "OK":
            rows.append({
                "filing": fid, "field": field_id, "claim_index": 0,
                "claim_text": "", "cited_text": "",
                "citation_found_in_filing": False,
                "claim_supported_by_citation": "", "material": "",
                "notes": f"{record['parse_status']}: {record.get('error') or 'model response did not parse as JSON'}",
            })
            continue

        claims = record["parsed_value"]
        if not isinstance(claims, list):
            rows.append({
                "filing": fid, "field": field_id, "claim_index": 0,
                "claim_text": "", "cited_text": "",
                "citation_found_in_filing": False,
                "claim_supported_by_citation": "", "material": "",
                "notes": "parsed value was not a list of claims",
            })
            continue

        filing_text_norm = _normalize_for_match(texts.get(fid, ""))
        for i, claim in enumerate(claims):
            claim_text = claim.get("claim", "") if isinstance(claim, dict) else ""
            cited_text = claim.get("citation", "") if isinstance(claim, dict) else ""
            found = bool(cited_text) and _normalize_for_match(cited_text) in filing_text_norm
            rows.append({
                "filing": fid, "field": field_id, "claim_index": i,
                "claim_text": claim_text, "cited_text": cited_text,
                "citation_found_in_filing": found,
                "claim_supported_by_citation": "", "material": "", "notes": "",
            })

    df = pd.DataFrame(rows, columns=WORKSHEET_COLUMNS)
    out_path = run_dir / "analysis_worksheet.csv"
    df.to_csv(out_path, index=False)
    print(f"analysis: {len(df)} claims across {num_analysis_cases} cases -> {out_path}")
    print("Fill in claim_supported_by_citation, material (TRUE/FALSE) and notes, then run --ingest.")
    return out_path


def _to_bool(value) -> bool | None:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return None
    s = str(value).strip().lower()
    if s in {"true", "t", "1", "yes"}:
        return True
    if s in {"false", "f", "0", "no"}:
        return False
    return None


def ingest(run_dir: Path) -> Path:
    worksheet_path = run_dir / "analysis_worksheet.csv"
    if not worksheet_path.exists():
        raise SystemExit(f"missing {worksheet_path} -- run --emit first, then hand-grade it.")

    df = pd.read_csv(worksheet_path)
    claims = df[df["claim_text"].fillna("").astype(str).str.len() > 0].copy()

    unfilled = claims[
        claims["claim_supported_by_citation"].isna() | claims["material"].isna()
    ]
    if len(unfilled):
        raise SystemExit(
            f"{len(unfilled)} claim(s) in {worksheet_path} are missing "
            f"claim_supported_by_citation or material. Fill in every row before ingesting."
        )

    claims["citation_found_in_filing"] = claims["citation_found_in_filing"].map(_to_bool).astype(bool)
    claims["claim_supported_by_citation"] = claims["claim_supported_by_citation"].map(_to_bool).astype(bool)
    claims["material"] = claims["material"].map(_to_bool).astype(bool)

    rows = []
    for field_id, group in claims.groupby("field"):
        n = len(group)
        fabrication_count = int((group["citation_found_in_filing"] == False).sum())  # noqa: E712
        rows.append({
            "field": field_id,
            "num_claims": n,
            "citation_validity_rate": round(group["citation_found_in_filing"].mean(), 3),
            "support_rate": round(group["claim_supported_by_citation"].mean(), 3),
            "materiality_rate": round(group["material"].mean(), 3),
            "fabrication_count": fabrication_count,
        })

    out = pd.DataFrame(rows, columns=[
        "field", "num_claims", "citation_validity_rate", "support_rate", "materiality_rate", "fabrication_count",
    ])
    out_path = run_dir / "analysis_scores.csv"
    out.to_csv(out_path, index=False)

    total_fabrications = out["fabrication_count"].sum()
    print(
        f"analysis: {len(claims)} claims graded, {total_fabrications} fabricated citations "
        f"(no valid quote found in filing) -> {out_path}"
    )
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or ingest the analysis grading worksheet.")
    parser.add_argument("--run", default=None, help="Run directory (default: latest under runs/).")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--emit", action="store_true")
    mode.add_argument("--ingest", action="store_true")
    args = parser.parse_args()

    run_dir = Path(args.run) if args.run else latest_run_dir()
    if args.emit:
        emit(run_dir)
    else:
        ingest(run_dir)


if __name__ == "__main__":
    main()
