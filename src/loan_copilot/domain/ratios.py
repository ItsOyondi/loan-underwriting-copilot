"""Ratio and pro-forma debt-service math. The model is not allowed to invent these."""

from __future__ import annotations


def _div(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def annual_payment(principal: float, annual_rate: float, years: int) -> float:
    """Level annual payment on a fixed-rate loan."""
    if principal <= 0 or years <= 0:
        return 0.0
    if annual_rate == 0:
        return round(principal / years, 2)
    growth = (1 + annual_rate) ** years
    payment = principal * (annual_rate * growth) / (growth - 1)
    return round(payment, 2)


def ratio_row(year: dict) -> dict:
    """One year of ratios from a statement line."""
    debt_service = year["interest_expense"] + year["principal_due"]
    return {
        "year": year["year"],
        "revenue": year["revenue"],
        "ebitda": year["ebitda"],
        "dscr": _div(year["ebitda"], debt_service),
        "debt_to_ebitda": _div(year["total_debt"], year["ebitda"]),
        "current_ratio": _div(year["current_assets"], year["current_liabilities"]),
        "interest_coverage": _div(year["ebitda"], year["interest_expense"]),
        "ebitda_margin": _div(year["ebitda"], year["revenue"]),
        "debt_service": debt_service,
        "total_debt": year["total_debt"],
    }


def calculate_ratios(years: list[dict]) -> list[dict]:
    """Ratios for each year, with revenue growth against the prior year."""
    rows = [ratio_row(year) for year in sorted(years, key=lambda item: item["year"])]
    previous_revenue = None
    for row in rows:
        if previous_revenue:
            row["revenue_growth"] = _div(row["revenue"] - previous_revenue, previous_revenue)
        else:
            row["revenue_growth"] = None
        previous_revenue = row["revenue"]
    return rows


def pro_forma_debt_service(latest: dict, amount: float, tenor_years: int, annual_rate: float) -> dict:
    """Latest-year ratios after adding the new loan's payment and principal."""
    new_payment = annual_payment(amount, annual_rate, tenor_years)
    debt_service = latest["interest_expense"] + latest["principal_due"] + new_payment
    total_debt = latest["total_debt"] + amount
    return {
        "new_annual_payment": new_payment,
        "dscr": _div(latest["ebitda"], debt_service),
        "debt_to_ebitda": _div(total_debt, latest["ebitda"]),
        "current_ratio": _div(latest["current_assets"], latest["current_liabilities"]),
        "interest_coverage": _div(latest["ebitda"], latest["interest_expense"]),
        "total_debt": total_debt,
        "debt_service": round(debt_service, 2),
    }
