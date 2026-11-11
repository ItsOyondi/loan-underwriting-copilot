"""Compare calculated ratios with the standard covenant set."""

from __future__ import annotations

from pathlib import Path

import yaml

from loan_copilot.config import DATA


def load_covenants(path: Path | None = None) -> list[dict]:
    file_path = path or DATA / "covenants.yaml"
    document = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    return list(document["covenants"])


def list_standard_covenants(loan_type: str = "commercial_term") -> list[dict]:
    """Return the covenant rules. `loan_type` selects the sample commercial set."""
    del loan_type
    return load_covenants()


def _passes(operator: str, value: float, threshold: float) -> bool:
    if operator == ">=":
        return value >= threshold
    if operator == "<=":
        return value <= threshold
    if operator == ">":
        return value > threshold
    if operator == "<":
        return value < threshold
    raise ValueError(f"Unsupported operator {operator}")


def _headroom(operator: str, value: float, threshold: float) -> float:
    if operator in {">=", ">"}:
        return round(value - threshold, 4)
    return round(threshold - value, 4)


def evaluate_covenants(ratios: dict, covenants: list[dict] | None = None, label: str = "current") -> list[dict]:
    """Test one ratio dictionary. Headroom is positive when the covenant passes."""
    rules = covenants if covenants is not None else load_covenants()
    results = []
    for rule in rules:
        value = ratios.get(rule["metric"])
        if value is None:
            results.append({**rule, "label": label, "value": None, "passed": False, "headroom": None})
            continue
        passed = _passes(rule["operator"], value, rule["threshold"])
        results.append(
            {
                **rule,
                "label": label,
                "value": value,
                "passed": passed,
                "headroom": _headroom(rule["operator"], value, rule["threshold"]),
            }
        )
    return results


def breach_names(results: list[dict]) -> list[str]:
    names = []
    for result in results:
        if not result["passed"]:
            prefix = "pro forma " if result.get("label") == "pro_forma" else ""
            names.append(f"{prefix}{result['name']}")
    return names
