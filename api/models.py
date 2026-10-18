"""Pydantic contract models. Field names are final (API_CONTRACT.md); this file is frozen after Task 1."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Scalar = bool | str | float | int | None
Source = Literal["jev", "user", "text", "employee", "approvals", "ledger", "derived", "rules", "answer", "product", "claude"]
Verdict = Literal["compliant", "violation", "undetermined"]


class _M(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


# ---- requests ----
class CheckRequest(_M):
    text: str
    employee_id: str
    amount: float | None = Field(None, gt=0)
    timestamp: str | None = None
    infer: bool = False  # opt in: a local `claude -p` call fills the facts the extractor leaves open


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


class Product(_M):
    """A store page the request linked to. Read once at /check; `error` says why nothing could be read."""
    url: str
    vendor: str
    title: str | None = None
    price: float | None = None
    category: str | None = None
    image: str | None = None
    error: str | None = None


class Case(_M):
    case_id: str
    created_at: str
    employee_id: str
    text: str
    policy_version: str
    verdict: Verdict
    facts: dict[str, Fact]
    violations: list[Violation]
    irs_notes: list[Violation] = []  # IRS rules not met; reported, never part of the verdict
    applied: list[str]
    fix: list[FixStep] | None
    questions: list[Question]
    explanation: str
    awaiting_approval: bool
    approval: Approval | None
    authorization: Authorization | None
    product: Product | None = None


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
    notes: list[str] = []  # IRS rules not met (ids); never part of the verdict
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


class LayersIn(_M):
    irs: bool  # the IRS layer on or off; the company layer is always on


class Witness(_M):
    """A purchase Z3 built (every fact set), re-proved by the engine."""
    facts: dict
    verdict: Verdict
    violations: list[str]
    because: dict[str, list[str]]  # rule -> the unsat core: the facts that decided it
    applied: list[str]
    also: list[str]  # other rules the witness trips, when no single-violation witness exists


class IrsRule(_M):
    id: str
    layer: str
    text: str
    cite: str
    url: str
    when: object
    require: object
    facts_used: list[str]
    prohibition: bool          # require is false: no purchase can satisfy it once its condition holds
    breaks: Witness | None
    holds: Witness | None      # None for a prohibition
    implied_by: list[str]      # company rules that already force it ([] = only the IRS layer catches it)
    ms: float


class IrsSummary(_M):
    rules: int
    implied_by_company: int
    irs_only: int
    prohibitions: int


class IrsReport(_M):
    enabled: bool
    policy_version: str
    rules: list[IrsRule]
    audit: "PolicyAudit"
    summary: IrsSummary


class RuleText(_M):
    text: str = Field(min_length=3)


class RuleIn(_M):
    text: str = Field(min_length=3)
    when: object
    require: object


class RuleDraft(_M):
    rule: dict          # {id, layer, text, when, require, custom}: post it back to POST /policy/rules as-is
    dead: bool          # the rule's condition can never hold
    conflicts: list[Conflict]  # only pairs that involve the draft


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


# ---- employees (dashboard signup) ----
class EmployeeIn(_M):
    name: str
    role: Literal["employee", "contractor", "intern"]
    manager_id: str = ""
    job_title: str = ""
    department: str = ""
    level: str = ""
    location: str = ""
    start_date: str = ""  # YYYY-MM-DD; blank = today (a new account is a new hire)


class Employee(_M):
    employee_id: str
    name: str
    role: str
    manager_id: str
    job_title: str = ""
    department: str = ""
    level: str = ""
    location: str = ""
    start_date: str = ""


class EmployeeList(_M):
    employees: list[Employee]


class ApplicableRule(_M):
    id: str
    layer: str
    text: str
    applies: bool            # can this rule ever fire for this person, given role and tenure
    days_left: int | None    # set when the rule stops applying after this many more days (probation rules)


class ApplicableOut(_M):
    employee: Employee
    facts: dict[str, Scalar]  # the standing facts the answer rests on: role, tenure_days
    rules: list[ApplicableRule]
