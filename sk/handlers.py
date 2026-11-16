"""Work that runs after a route is chosen.

The route name is the dictionary key. Lookup replaces a chain of if statements.
"""

from __future__ import annotations


def open_credit_officer_file(case_summary: str) -> str:
    return f"Credit Officer file opened for {case_summary}"


def open_senior_credit_officer_file(case_summary: str) -> str:
    return f"Senior Credit Officer file opened for {case_summary}"


def schedule_credit_committee(case_summary: str) -> str:
    return f"Credit Committee review scheduled for {case_summary}"


def schedule_board_committee(case_summary: str) -> str:
    return f"Board Credit Committee review scheduled for {case_summary}"


def missing_route(case_summary: str) -> str:
    return f"No handler is registered for this case: {case_summary}"


HANDLERS = {
    "Credit Officer": open_credit_officer_file,
    "Senior Credit Officer": open_senior_credit_officer_file,
    "Credit Committee": schedule_credit_committee,
    "Board Credit Committee": schedule_board_committee,
}


def invoke_route(route: str, case_summary: str) -> str:
    """Call the function registered for this route."""
    return HANDLERS.get(route, missing_route)(case_summary)
