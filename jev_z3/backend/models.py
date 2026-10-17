"""Versioned interchange models for Person A's API and Person B's adapters."""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, model_validator


FACT_TYPES: dict[str, str | tuple[str, ...]] = {
    "amount_cents": "int", "days_since_purchase": "int",
    "role": ("employee", "contractor", "intern"),
    "expense_kind": ("meal", "entertainment", "rideshare", "airfare", "hotel", "software", "equipment", "office", "other"),
    "coded_account": ("meals_50", "meals_100", "entertainment_0", "travel", "office", "other"),
    "pre_approved": "bool", "receipt_required": "bool", "receipt_attached": "bool",
    "receipt_timely": "bool", "client_present": "bool", "at_company_event": "bool",
    "business_purpose": "bool", "employee_present": "bool", "lavish": "bool",
    "qualified_employee_recreation": "bool", "other_tax_exception": "bool",
    "separately_stated_meal": "bool", "mixed_entertainment": "bool",
}
DERIVED = {"amount_cents", "days_since_purchase"}
Verdict = Literal["compliant", "violation", "undetermined", "not_applicable"]


def digest(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def money_cents(value: str) -> int:
    number = Decimal(str(value)) * 100
    if not number.is_finite() or number != number.to_integral_value():
        raise ValueError(f"Expected exact two-decimal money, got {value!r}")
    return int(number)


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Fact(Model):
    value: StrictBool | StrictInt | StrictStr | None = None
    source: str
    evidence_id: str | None = None
    probability: float | None = Field(default=None, ge=0, le=1)


def validate_facts(facts: dict[str, Fact]) -> None:
    for key, fact in facts.items():
        spec = FACT_TYPES.get(key)
        if spec is None:
            raise ValueError(f"Unsupported fact: {key}")
        value = fact.value
        if value is None:
            continue
        if spec == "bool" and type(value) is not bool:
            raise ValueError(f"{key} must be boolean or unknown")
        if spec == "int" and (type(value) is not int or value < 0):
            raise ValueError(f"{key} must be a nonnegative integer or unknown")
        if isinstance(spec, tuple) and value not in spec:
            raise ValueError(f"Invalid {key}: {value!r}")


class AccountingLine(Model):
    account_id: str | None = None
    account_name: str | None = None
    item_id: str | None = None
    original_item_id: str | None = None
    description: str = ""
    amount_cents: int = Field(strict=True)


class Settlement(Model):
    payment_id: str
    bank_transaction_ids: list[str]
    settlement_date: date
    allocated_cents: int = Field(ge=0, strict=True)


class Approval(Model):
    evidence_id: str
    approver_id: str
    approved: bool
    approved_at: datetime

    @model_validator(mode="after")
    def aware(self):
        if self.approved_at.tzinfo is None:
            raise ValueError("Approval timestamp must include a timezone")
        return self


class Receipt(Model):
    evidence_id: str
    submitted_date: date


class PurchaseCase(Model):
    schema_version: str = "1"
    case_id: str
    company_id: str
    policy_version: str = "demo-2026-10-17-v1"
    origin: Literal["original", "synthetic"]
    description: str
    amount_cents: int = Field(ge=0, strict=True)
    currency: Literal["USD"] = "USD"
    purchase_date: date
    purchase_at: datetime | None = None
    as_of_date: date
    stage: Literal["requested", "posted"] = "posted"
    vendor_id: str | None = None
    vendor_name: str | None = None
    employee_id: str | None = None
    facts: dict[str, Fact] = Field(default_factory=dict)
    accounting_lines: list[AccountingLine] = Field(default_factory=list)
    settlements: list[Settlement] = Field(default_factory=list)
    approvals: list[Approval] = Field(default_factory=list)
    receipts: list[Receipt] = Field(default_factory=list)
    source_documents: list[str] = Field(default_factory=list)
    provenance: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_case(self):
        validate_facts(self.facts)
        if DERIVED.intersection(self.facts):
            raise ValueError("Amount and age are derived from authoritative case fields")
        if self.as_of_date < self.purchase_date and self.stage == "posted":
            raise ValueError("Posted purchase cannot occur after observation date")
        if self.purchase_at and (self.purchase_at.tzinfo is None or self.purchase_at.date() != self.purchase_date):
            raise ValueError("Purchase timestamp must have a timezone and agree with purchase_date")
        return self

    def resolved_facts(self) -> dict[str, Fact]:
        facts = dict(self.facts)
        facts["amount_cents"] = Fact(value=self.amount_cents, source="case.amount_cents")
        facts["days_since_purchase"] = Fact(value=max(0, (self.as_of_date-self.purchase_date).days), source="case.dates")
        visible = [a for a in self.approvals if a.approved_at.date() <= self.as_of_date]
        if visible:
            eligible = visible
            if self.stage == "posted":
                # An approval after purchase cannot overwrite the historical state.
                prior = [a for a in visible if a.approved_at <= self.purchase_at] if self.purchase_at else [a for a in visible if a.approved_at.date() <= self.purchase_date]
                eligible = prior or visible
            approval = max(eligible, key=lambda a: a.approved_at)
            value: bool | None = approval.approved
            if value and self.stage == "posted":
                if self.purchase_at:
                    value = approval.approved_at <= self.purchase_at
                elif approval.approved_at.date() == self.purchase_date:
                    value = None  # Date precision cannot prove pre-approval.
                else:
                    value = approval.approved_at.date() < self.purchase_date
            facts["pre_approved"] = Fact(value=value, source="approval_record", evidence_id=approval.evidence_id)
        receipts = [r for r in self.receipts if self.purchase_date <= r.submitted_date <= self.as_of_date]
        if receipts:
            receipt = min(receipts, key=lambda r: r.submitted_date)
            facts["receipt_attached"] = Fact(value=True, source="receipt_record", evidence_id=receipt.evidence_id)
            facts["receipt_timely"] = Fact(value=(receipt.submitted_date-self.purchase_date).days <= 60, source="receipt_record", evidence_id=receipt.evidence_id)
        return facts


class RuleResult(Model):
    rule_id: str
    layer: Literal["company", "tax"]
    verdict: Verdict
    missing_facts: list[str] = Field(default_factory=list)


class LayerResult(Model):
    verdict: Verdict | None = None
    violated_rule_ids: list[str] = Field(default_factory=list)
    applicable_rule_ids: list[str] = Field(default_factory=list)
    rules: list[RuleResult] = Field(default_factory=list)


class EvaluationResult(Model):
    schema_version: str = "1"
    evaluator_version: str = "1.0"
    case_id: str
    company_id: str
    policy_version: str
    policy_hash: str
    facts_hash: str
    status: Literal["ok", "unsupported", "conflicting_policy", "error"] = "ok"
    company: LayerResult = Field(default_factory=LayerResult)
    tax: LayerResult = Field(default_factory=LayerResult)
    questions: list[dict[str, Any]] = Field(default_factory=list)
    proposed_fixes: list[dict[str, Any]] = Field(default_factory=list)
    diagnostics: list[str] = Field(default_factory=list)
    facts: dict[str, Fact] = Field(default_factory=dict)
