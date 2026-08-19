"""Loaders for config/fields.yaml and config/filings.yaml."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FIELDS_PATH = REPO_ROOT / "config" / "fields.yaml"
DEFAULT_FILINGS_PATH = REPO_ROOT / "config" / "filings.yaml"


def filing_id(ticker: str, fy: Any) -> str:
    return f"{ticker}_{fy}"


def load_fields_config(path: Path | str = DEFAULT_FIELDS_PATH) -> dict:
    """Load field definitions. Populates named_operational_metrics' `keys`
    from the top-level `operational_metrics` list so that field stays
    configurable in one place."""
    with open(path) as f:
        cfg = yaml.safe_load(f) or {}

    cfg = copy.deepcopy(cfg)
    metrics = cfg.get("operational_metrics", [])
    for field in cfg.get("extraction_fields", []):
        if field.get("id") == "named_operational_metrics":
            field["keys"] = list(metrics)
    return cfg


def load_filings_config(path: Path | str = DEFAULT_FILINGS_PATH) -> list[dict]:
    with open(path) as f:
        cfg = yaml.safe_load(f) or {}
    filings = cfg.get("filings") or []
    for entry in filings:
        entry.setdefault("file", f"{entry['ticker']}_{entry['fy']}.pdf")
    return filings


def extraction_field_by_id(fields_cfg: dict, field_id: str) -> dict:
    for field in fields_cfg.get("extraction_fields", []):
        if field["id"] == field_id:
            return field
    raise KeyError(f"unknown extraction field id: {field_id}")


def analysis_field_by_id(fields_cfg: dict, field_id: str) -> dict:
    for field in fields_cfg.get("analysis_fields", []):
        if field["id"] == field_id:
            return field
    raise KeyError(f"unknown analysis field id: {field_id}")


def value_shape_description(field: dict) -> str:
    """Human-readable description of the required JSON shape, used in prompts."""
    vt = field["value_type"]
    unit = field.get("unit", "")
    if vt == "number":
        zero_note = " Use 0 if none occurred." if field.get("zero_if_none") else ""
        null_note = " Use null if not disclosed."
        return f'A single JSON number, in {unit}.{zero_note}{null_note}'
    if vt == "dict_numeric":
        keys = field.get("keys") or []
        keys_desc = ", ".join(keys) if keys else "(operator-configured keys)"
        return (
            f'A JSON object with exactly these keys: {keys_desc}. '
            f"Each value is a number in {unit}, or null if that key is not disclosed. "
            f'Example: {{"key_name": 12.3, "other_key": null}}'
        )
    if vt == "customer_list":
        return (
            'A JSON array of objects, each {"customer_name_or_descriptor": string, '
            '"pct_of_revenue": number}. Use an empty array [] if no customer is '
            "disclosed at or above the 10% threshold."
        )
    raise ValueError(f"unknown value_type: {vt}")
