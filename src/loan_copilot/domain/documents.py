"""Read the four case documents. Numbers come from a JSON block in each file."""

from __future__ import annotations

import json
import re
from pathlib import Path

REQUIRED = (
    "borrower_request.md",
    "financial_statements.md",
    "management_report.md",
    "credit_report.md",
)

_JSON_BLOCK = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


def parse_document(path: str | Path) -> dict:
    """Return the prose and, when present, the JSON facts in the file."""
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    match = _JSON_BLOCK.search(text)
    data = json.loads(match.group(1)) if match else {}
    data["text"] = text
    data["source"] = file_path.name
    return data


def load_case(case_dir: str | Path) -> tuple[dict[str, dict], list[str]]:
    """Load the four documents. The second value is the list of missing file names."""
    folder = Path(case_dir)
    missing = [name for name in REQUIRED if not (folder / name).is_file()]
    loaded = {}
    for name in REQUIRED:
        path = folder / name
        if path.is_file():
            loaded[name] = parse_document(path)
    return loaded, missing
