"""Delegated approval authority from amount and risk grade."""

from __future__ import annotations

from pathlib import Path

import yaml

from loan_copilot.config import DATA


def load_matrix(path: Path | None = None) -> list[dict]:
    file_path = path or DATA / "authority_matrix.yaml"
    document = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    return list(document["bands"])


def get_authority_matrix() -> list[dict]:
    """Return the amount and grade bands used to choose an approver."""
    return load_matrix()


def grade_band(risk_grade: int) -> str:
    if risk_grade <= 4:
        return "1-4"
    if risk_grade <= 6:
        return "5-6"
    return "7+"


def lookup_authority(amount: float, risk_grade: int, bands: list[dict] | None = None) -> str:
    """Return the approver level for this amount and grade."""
    band_name = grade_band(risk_grade)
    chosen = bands if bands is not None else load_matrix()
    for band in chosen:
        cap = band["max_amount"]
        if cap is None or amount <= cap:
            return band["grades"][band_name]
    return chosen[-1]["grades"][band_name]
