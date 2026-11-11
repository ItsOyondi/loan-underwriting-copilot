"""Pydantic results produced by the seven agents."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class IntakeResult(BaseModel):
    borrower_id: str
    borrower_name: str
    legal_name: str
    industry: str
    requested_amount: float
    tenor_years: int
    purpose: str
    collateral: str
    bureau_score: int
    years: list[dict]
    facilities: list[dict] = Field(default_factory=list)
    related_parties: list[dict] = Field(default_factory=list)
    name_matches_customer: bool
    management_excerpt: str = ""
    summary: str


class FinancialAssessment(BaseModel):
    ratios: list[dict]
    strengths: list[str]
    weaknesses: list[str]
    narrative: str


class CovenantResult(BaseModel):
    current: list[dict]
    pro_forma: list[dict]
    breaches: list[str]
    narrative: str


class PolicyContext(BaseModel):
    policies: list[dict]
    precedents: list[dict]
    narrative: str


class RiskAssessment(BaseModel):
    risk_grade: int
    recommendation: Literal["approve", "approve_with_conditions", "decline"]
    key_risks: list[str]
    mitigants: list[str]
    policy_exceptions: list[str]
    narrative: str


class CreditMemo(BaseModel):
    markdown: str
    recommendation: str


class ApprovalRoute(BaseModel):
    approver_level: str
    amount: float
    risk_grade: int
    conditions: list[str]
    justification: str
