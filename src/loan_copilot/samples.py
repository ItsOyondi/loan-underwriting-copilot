"""Check the sample cases against the catalog, then run each one."""

from __future__ import annotations

import json

from loan_copilot.config import DATA
from loan_copilot.domain.covenants import breach_names, evaluate_covenants
from loan_copilot.domain.documents import REQUIRED, load_case
from loan_copilot.domain.ratios import calculate_ratios


def load_catalog() -> dict:
    return json.loads((DATA / "catalog.json").read_text(encoding="utf-8"))


def _borrower_ids() -> set[str]:
    rows = json.loads((DATA / "borrowers.json").read_text(encoding="utf-8"))
    return {row["borrowerId"] for row in rows}


def validate_catalog() -> list[str]:
    """Return human-readable problems. An empty list means the fixtures agree with the tools."""
    catalog = load_catalog()
    known = _borrower_ids()
    errors: list[str] = []
    seen: set[str] = set()
    for case in catalog["cases"]:
        case_id = case["id"]
        if case_id in seen:
            errors.append(f"{case_id}: duplicate catalog id")
        seen.add(case_id)
        folder = DATA / "sample_cases" / case_id
        if not folder.is_dir():
            errors.append(f"{case_id}: folder missing")
            continue
        documents, missing = load_case(folder)
        expected_missing = case.get("missing", [])
        if missing != expected_missing:
            errors.append(f"{case_id}: missing files {missing}, catalog says {expected_missing}")
        expect = case["expect"]
        if expect.get("stop_reason") == "UNKNOWN_CUSTOMER":
            if case["borrower_id"] in known:
                errors.append(f"{case_id}: unknown-customer fixture is in borrowers.json")
        elif case["borrower_id"] not in known:
            errors.append(f"{case_id}: borrower {case['borrower_id']} is not in borrowers.json")
        request = documents.get("borrower_request.md")
        if request:
            if request.get("borrower_id") != case["borrower_id"]:
                errors.append(f"{case_id}: request borrower id does not match the catalog")
            if request.get("borrower_name") != case["borrower_name"]:
                errors.append(f"{case_id}: request borrower name does not match the catalog")
            if request.get("requested_amount") != case["requested_amount"]:
                errors.append(f"{case_id}: request amount does not match the catalog")
        statements = documents.get("financial_statements.md")
        if statements and "latest_ratios" in case:
            latest = calculate_ratios(statements["years"])[-1]
            for metric, expected in case["latest_ratios"].items():
                if latest.get(metric) != expected:
                    errors.append(f"{case_id}: {metric} is {latest.get(metric)}, catalog says {expected}")
            if "current_breach_count" in expect:
                breaches = breach_names(evaluate_covenants(latest))
                if len(breaches) != expect["current_breach_count"]:
                    errors.append(f"{case_id}: current breaches {breaches}")
        elif not statements and set(REQUIRED) - set(expected_missing) > {"management_report.md"}:
            errors.append(f"{case_id}: financial statements are required unless the file is listed as missing")
    return errors


def outcome_errors(view: dict, case: dict) -> list[str]:
    """Compare one finished case view with the catalog."""
    case_id = case["id"]
    expect = case["expect"]
    errors = []
    if view.get("status") != expect["auto_status"]:
        errors.append(f"{case_id}: status {view.get('status')}, expected {expect['auto_status']}")
    if view.get("stop_reason") != expect.get("stop_reason"):
        errors.append(f"{case_id}: stop {view.get('stop_reason')}, expected {expect.get('stop_reason')}")
    if expect.get("stop_reason"):
        return errors
    risk = view.get("risk") or {}
    route = view.get("route") or {}
    intake = view.get("intake") or {}
    checks = {
        "recommendation": risk.get("recommendation"),
        "risk_grade": risk.get("risk_grade"),
        "approver_level": route.get("approver_level"),
        "name_matches": intake.get("name_matches_customer"),
    }
    for field, actual in checks.items():
        if actual != expect[field]:
            errors.append(f"{case_id}: {field} is {actual}, expected {expect[field]}")
    if expect["name_matches"] is False:
        risks = " ".join(risk.get("key_risks") or [])
        if "does not match" not in risks:
            errors.append(f"{case_id}: name mismatch was not recorded as a risk")
    return errors
