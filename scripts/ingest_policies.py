"""Policies are read from data/policies for the offline MVP.

Point USE_AZURE_SEARCH at an index you loaded with the same markdown when you move off local files.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    files = sorted((ROOT / "data" / "policies").glob("*.md"))
    print(f"{len(files)} policy files are ready in data/policies:")
    for path in files:
        print(f"  {path.name}")


if __name__ == "__main__":
    main()
