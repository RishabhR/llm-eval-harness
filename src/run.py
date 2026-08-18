"""Run extraction or analysis prompts across the filing set.

    python -m src.run --fields extraction --prompt prompts/extraction_v1.txt \\
        --model claude-sonnet-5 --out runs/{timestamp}/

Reads ANTHROPIC_API_KEY from the environment. Never hardcode a key here.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import anthropic

from src import cache
from src.config import (
    REPO_ROOT,
    analysis_field_by_id,
    extraction_field_by_id,
    filing_id,
    load_fields_config,
    load_filings_config,
    value_shape_description,
)
from src.load import chunk_text, load_filing

MAX_CONCURRENCY = 3
MAX_RETRIES = 5
MAX_TOKENS_OUT = 2048
# Chunking is a safety valve, not the common path -- a 10-K's full text
# normally fits comfortably in one call. See load.chunk_text.
DEFAULT_MAX_TOKENS_PER_CHUNK = 150_000

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def strip_json_fences(text: str) -> str:
    return _FENCE_RE.sub("", text.strip()).strip()


def build_extraction_prompt(template: str, field: dict, filing_text: str) -> str:
    return (
        template.replace("<<FIELD_NAME>>", field["name"])
        .replace("<<FIELD_WHERE>>", field.get("where", ""))
        .replace("<<VALUE_SHAPE>>", value_shape_description(field))
        .replace("<<FILING_TEXT>>", filing_text)
    )


def build_analysis_prompt(template: str, field: dict, filing_text: str) -> str:
    return (
        template.replace("<<FIELD_NAME>>", field["name"])
        .replace("<<ASKS_FOR>>", field.get("asks_for", "").strip())
        .replace("<<FILING_TEXT>>", filing_text)
    )


def call_model(client: anthropic.Anthropic, model: str, prompt: str) -> tuple[str, int, int, float]:
    """Returns (raw_text, input_tokens, output_tokens, latency_seconds)."""
    start = time.perf_counter()
    delay = 1.0
    last_error: Exception | None = None

    for attempt in range(MAX_RETRIES):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=MAX_TOKENS_OUT,
                messages=[{"role": "user", "content": prompt}],
            )
            latency = time.perf_counter() - start
            text = "".join(
                block.text for block in response.content if getattr(block, "type", None) == "text"
            )
            return text, response.usage.input_tokens, response.usage.output_tokens, latency
        except (anthropic.RateLimitError, anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
            last_error = exc
            if attempt == MAX_RETRIES - 1:
                break
            time.sleep(delay)
            delay = min(delay * 2, 60.0)

    raise RuntimeError(f"model call failed after {MAX_RETRIES} attempts: {last_error}")


def parse_response(raw_text: str) -> tuple[object | None, str]:
    """Returns (parsed_value_or_None, parse_status)."""
    try:
        return json.loads(strip_json_fences(raw_text)), "OK"
    except (json.JSONDecodeError, ValueError):
        return None, "PARSE_ERROR"


def build_cases(fields_kind: str, fields_cfg: dict, filings: list[dict]) -> list[tuple[dict, dict]]:
    key = "extraction_fields" if fields_kind == "extraction" else "analysis_fields"
    fields = fields_cfg[key]
    return [(f, field) for f in filings for field in fields]


def run_one_case(
    client: anthropic.Anthropic,
    fields_kind: str,
    filing_entry: dict,
    field: dict,
    prompt_template: str,
    model: str,
    prompt_path: str,
    max_tokens_per_chunk: int,
) -> list[dict]:
    fid = filing_id(filing_entry["ticker"], filing_entry["fy"])
    records = []

    try:
        full_text = load_filing(filing_entry["ticker"], filing_entry["fy"])
    except FileNotFoundError as exc:
        return [
            {
                "filing": fid,
                "field": field["id"],
                "prompt_file": prompt_path,
                "model": model,
                "chunk_index": 0,
                "num_chunks": 0,
                "raw_response": None,
                "parsed_value": None,
                "parse_status": "LOAD_ERROR",
                "error": str(exc),
                "latency_seconds": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cached": False,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ]

    chunks = chunk_text(full_text, max_tokens=max_tokens_per_chunk)
    if not chunks:
        chunks = [full_text]

    for chunk_index, chunk in enumerate(chunks):
        if fields_kind == "extraction":
            prompt = build_extraction_prompt(prompt_template, field, chunk)
        else:
            prompt = build_analysis_prompt(prompt_template, field, chunk)

        key = cache.cache_key(fid, field["id"], prompt, model, chunk_index)
        cached_entry = cache.get(key)

        if cached_entry is not None:
            raw_text = cached_entry["raw_response"]
            input_tokens = cached_entry["input_tokens"]
            output_tokens = cached_entry["output_tokens"]
            latency = 0.0
            cached = True
        else:
            raw_text, input_tokens, output_tokens, latency = call_model(client, model, prompt)
            cache.set(
                key,
                {
                    "raw_response": raw_text,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                },
            )
            cached = False

        parsed_value, parse_status = parse_response(raw_text)

        records.append(
            {
                "filing": fid,
                "field": field["id"],
                "prompt_file": prompt_path,
                "model": model,
                "chunk_index": chunk_index,
                "num_chunks": len(chunks),
                "raw_response": raw_text,
                "parsed_value": parsed_value,
                "parse_status": parse_status,
                "error": None,
                "latency_seconds": round(latency, 3),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cached": cached,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Run eval prompts across the filing set.")
    parser.add_argument("--fields", choices=["extraction", "analysis"], required=True)
    parser.add_argument("--prompt", required=True, help="Path to a prompt template file.")
    parser.add_argument("--model", required=True, help="Anthropic model id.")
    parser.add_argument("--out", default=None, help="Output directory (default: runs/{timestamp}/).")
    parser.add_argument("--max-concurrency", type=int, default=MAX_CONCURRENCY)
    parser.add_argument("--max-tokens-per-chunk", type=int, default=DEFAULT_MAX_TOKENS_PER_CHUNK)
    args = parser.parse_args()

    max_concurrency = min(args.max_concurrency, MAX_CONCURRENCY)

    prompt_path = Path(args.prompt)
    prompt_template = prompt_path.read_text()

    fields_cfg = load_fields_config()
    filings = load_filings_config()
    if not filings:
        print("No filings configured in config/filings.yaml. Nothing to run.", file=sys.stderr)
        sys.exit(1)

    cases = build_cases(args.fields, fields_cfg, filings)

    out_dir = Path(args.out) if args.out else REPO_ROOT / "runs" / datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "raw_outputs.jsonl"

    client = anthropic.Anthropic()
    write_lock = threading.Lock()

    stats = {"cases": 0, "cache_hits": 0, "parse_errors": 0, "load_errors": 0, "input_tokens": 0, "output_tokens": 0}
    start_time = time.perf_counter()

    # Append, not overwrite: an extraction run and an analysis run are meant to
    # share one runs/{timestamp}/ directory (pass the same --out to both), so
    # report.py can see both halves.
    with open(out_path, "a") as out_file:

        def handle(filing_entry: dict, field: dict) -> None:
            records = run_one_case(
                client, args.fields, filing_entry, field, prompt_template,
                args.model, str(prompt_path), args.max_tokens_per_chunk,
            )
            with write_lock:
                for record in records:
                    out_file.write(json.dumps(record) + "\n")
                    stats["cases"] += 1
                    stats["cache_hits"] += int(record["cached"])
                    stats["parse_errors"] += int(record["parse_status"] == "PARSE_ERROR")
                    stats["load_errors"] += int(record["parse_status"] == "LOAD_ERROR")
                    stats["input_tokens"] += record["input_tokens"]
                    stats["output_tokens"] += record["output_tokens"]
                out_file.flush()

        with ThreadPoolExecutor(max_workers=max_concurrency) as pool:
            futures = [pool.submit(handle, filing_entry, field) for filing_entry, field in cases]
            for future in as_completed(futures):
                future.result()  # re-raise any exception

    elapsed = time.perf_counter() - start_time
    print(
        f"[{args.fields}] {len(cases)} cases -> {stats['cases']} records "
        f"({stats['cache_hits']} cached, {stats['parse_errors']} parse errors, "
        f"{stats['load_errors']} load errors) in {elapsed:.1f}s, "
        f"{stats['input_tokens']}+{stats['output_tokens']} tokens -> {out_path}"
    )


if __name__ == "__main__":
    main()
