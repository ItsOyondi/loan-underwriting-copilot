"""Precedent summaries are read from data/precedents for the offline MVP."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    files = sorted((ROOT / "data" / "precedents").glob("*.md"))
    print(f"{len(files)} precedent files are ready in data/precedents:")
    for path in files:
        print(f"  {path.name}")


if __name__ == "__main__":
    main()
