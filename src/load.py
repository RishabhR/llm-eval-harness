"""Filing text loading, naive section splitting, and paragraph-boundary chunking."""
from __future__ import annotations

import re
import sys
import warnings
from pathlib import Path

from pypdf import PdfReader

from src.config import REPO_ROOT, filing_id

FILINGS_DIR = REPO_ROOT / "filings"

MIN_CHARS_PER_PAGE = 500

# Common 10-K item headers, in the order they normally appear.
SECTION_HEADERS = ["1", "1A", "1B", "7", "7A", "8"]
_SECTION_RE = re.compile(
    r"^\s*item\s+(1a|1b|7a|1|7|8)\.?\s", re.IGNORECASE | re.MULTILINE
)


def _find_filing_path(ticker: str, fy, filings_dir: Path) -> Path:
    fid = filing_id(ticker, fy)
    for ext in (".pdf", ".txt"):
        candidate = filings_dir / f"{fid}{ext}"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"no filing found for {fid} in {filings_dir} (expected {fid}.pdf or {fid}.txt)"
    )


def _load_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(pages)

    num_pages = max(len(pages), 1)
    avg_chars_per_page = sum(len(p) for p in pages) / num_pages
    if avg_chars_per_page < MIN_CHARS_PER_PAGE:
        message = (
            f"\n{'!' * 70}\n"
            f"WARNING: {path.name} extracted only {avg_chars_per_page:.0f} chars/page "
            f"(threshold {MIN_CHARS_PER_PAGE}). This filing may be scanned/image-based "
            f"and effectively unusable for extraction. Consider OCR-ing it first.\n"
            f"{'!' * 70}\n"
        )
        print(message, file=sys.stderr)
        warnings.warn(message)

    return text


def load_filing(ticker: str, fy, filings_dir: Path | None = None) -> str:
    filings_dir = Path(filings_dir) if filings_dir else FILINGS_DIR
    path = _find_filing_path(ticker, fy, filings_dir)
    if path.suffix.lower() == ".pdf":
        return _load_pdf_text(path)
    return path.read_text(encoding="utf-8", errors="replace")


def split_sections(text: str) -> dict[str, str]:
    """Naive convenience splitter on common 10-K item headers. Returns a dict
    keyed by header label (e.g. "1A") to that section's text. Best-effort only
    -- the default path for prompts is full text, not these sections."""
    matches = list(_SECTION_RE.finditer(text))
    if not matches:
        return {}

    sections: dict[str, str] = {}
    for i, match in enumerate(matches):
        label = match.group(1).upper()
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        # Keep the longest match if a header label recurs (e.g. referenced twice).
        chunk = text[start:end]
        if label not in sections or len(chunk) > len(sections[label]):
            sections[label] = chunk
    return sections


def chunk_text(text: str, max_tokens: int = 6000, overlap_tokens: int = 200) -> list[str]:
    """Split on paragraph boundaries, keeping each chunk under max_tokens
    (approximated as whitespace-delimited words, since no tokenizer dependency
    is in scope). Each chunk after the first is prefixed with the trailing
    overlap_tokens words of the previous chunk for context continuity."""
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        return [text] if text.strip() else []

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para.split())
        if current and current_len + para_len > max_tokens:
            chunks.append("\n\n".join(current))
            overlap_words = "\n\n".join(current).split()[-overlap_tokens:]
            current = [" ".join(overlap_words)] if overlap_words else []
            current_len = len(overlap_words)
        current.append(para)
        current_len += para_len

    if current:
        chunks.append("\n\n".join(current))
    return chunks
