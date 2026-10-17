"""Pydantic contract models. Field names are final (API_CONTRACT.md); this file is frozen after Task 1."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Scalar = bool | str | float | int | None
Source = Literal["jev", "user", "text", "employee", "approvals", "ledger", "derived", "rules", "answer"]
Verdict = Literal["compliant", "violation", "undetermined"]


class _M(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


# ---- requests ----
class CheckRequest(_M):
    text: str
    employee_id: str
    amount: float | None = Field(None, gt=0)
    timestamp: str | None = None


class AnswerRequest(_M):
    fact: str
    value: bool | str | float


class ApproveRequest(_M):
    approver: str
    approved: bool


class AuditRequest(_M):
    company: str


class BankRule(_M):
    id: str
    contains: list[str]
    amount_min: float | None = None
    amount_max: float | None = None
    category: str


class BankRulesRequest(_M):
    rules: list[BankRule]


# ---- case ----
class Fact(_M):
    value: Scalar
    source: Source
    p: float | None = None


class Violation(_M):
    rule: str
    layer: str
    text: str
    because: list[str]


class FixStep(_M):
    fact: str
    from_: Scalar = Field(alias="from")
    to: Scalar


class Question(_M):
    fact: str
    text: str
    p: float | None = None
    options: list[str] | None = None


class Authorization(_M):
    auth_id: str
    amount_limit: float
    merchant_category: str
    expires_at: str
    proof_hash: str


class Approval(_M):
    approver: str
    approved: bool
    at: str


class Case(_M):
    case_id: str
    created_at: str
    employee_id: str
    text: str
    policy_version: str
    verdict: Verdict
    facts: dict[str, Fact]
    violations: list[Violation]
    applied: list[str]
    fix: list[FixStep] | None
    questions: list[Question]
    explanation: str
    awaiting_approval: bool
    approval: Approval | None
    authorization: Authorization | None


class CaseList(_M):
    cases: list[Case]


# ---- ledger / audit ----
class LedgerRow(_M):
    txn_id: str
    company: str
    employee_id: str
    vendor: str
    memo: str
    amount: float
    timestamp: str
    qb_category: str
    coded_account: str
    verdict: Verdict
    violations: list[str]
    case: Case | None


class LedgerOut(_M):
    transactions: list[LedgerRow]
    total: int


class RuleCount(_M):
    rule: str
    text: str
    count: int


class AuditSummary(_M):
    company: str
    policy_version: str
    n: int
    by_verdict: dict[str, int]
    by_rule: list[RuleCount]
    top_violations: list[LedgerRow]
    elapsed_ms: int


class ReloadOut(_M):
    transactions: int
    employees: int
    extractions: int
    approvals: int
    skipped: list


# ---- policy / bank rules ----
class PolicyOut(_M):
    version: str
    rules: list[dict]
    facts: dict


class Conflict(_M):
    a: str
    b: str
    example: dict


class PolicyAudit(_M):
    dead: list[str]
    conflicts: list[Conflict]


class Shadowed(_M):
    rule: str
    by: list[str]


class Overlap(_M):
    a: str
    b: str
    example: dict


class BankRulesOut(_M):
    shadowed: list[Shadowed]
    overlaps: list[Overlap]


# ---- eval / health ----
class EvalSystem(_M):
    name: str
    accuracy: float
    citation_f1: float
    rerun_agreement: float
    median_latency_ms: float
    cost_per_1k_usd: float
    questions_per_txn: float


class EvalOut(_M):
    as_of: str | None
    n_heldout: int
    systems: list[EvalSystem]


class Health(_M):
    ok: bool
    policy_version: str
    stub: bool
