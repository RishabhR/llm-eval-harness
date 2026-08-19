"""Local response cache, keyed by hash of (filing, field, prompt, model).

Cache lives in .cache/ at the repo root (gitignored). Each entry is a JSON
file so it can be inspected by hand if needed.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from src.config import REPO_ROOT

CACHE_DIR = REPO_ROOT / ".cache"


def cache_key(filing_id: str, field_id: str, prompt_text: str, model: str, chunk_index: int = 0) -> str:
    payload = f"{filing_id}|{field_id}|{model}|{chunk_index}|{prompt_text}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get(key: str) -> dict[str, Any] | None:
    path = CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def set(key: str, value: dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{key}.json"
    with open(path, "w") as f:
        json.dump(value, f)
