"""
Data models and schemas for Jev classification and Z3 parameter proofs.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RuleDomain(str, Enum):
    EXPENSE_POLICY = "expense_policy"
    QUICKBOOKS_ROUTING = "quickbooks_routing"
    PROCUREMENT_PO = "procurement_po"
    TAX_COMPLIANCE = "tax_compliance"
    ANTI_FRAUD_SPLIT = "anti_fraud_split"


class TargetScope(str, Enum):
    SINGLE_TRANSACTION = "single_transaction"
    LINE_ITEM = "line_item"
    DAILY_AGGREGATE = "daily_aggregate"
    MONTHLY_RECURRING = "monthly_recurring"
    PER_ATTENDEE = "per_attendee"


class SpendCategory(str, Enum):
    MEALS_ENTERTAINMENT = "meals_entertainment"
    SOFTWARE_SAAS = "software_saas"
    TRAVEL_LODGING = "travel_lodging"
    OFFICE_SUPPLIES = "office_supplies"
    CONTRACTOR_SERVICES = "contractor_services"
    HARDWARE_EQUIPMENT = "hardware_equipment"
    GENERAL_SPEND = "general_spend"
    ANY = "any"


class ComparisonOperator(str, Enum):
    GREATER_THAN = ">"
    GREATER_EQUAL = ">="
    LESS_THAN = "<"
    LESS_EQUAL = "<="
    EQUALS = "=="
    BETWEEN = "between"
    ALWAYS = "always"


class RuleAction(str, Enum):
    AUTO_APPROVE = "auto_approve"
    REQUIRE_APPROVAL = "require_approval"
    FLAG_AUDIT = "flag_audit"
    REJECT = "reject"
    ASSIGN_ACCOUNT = "assign_account"


class Z3RuleParameters(BaseModel):
    """
    Structured parameters extracted by the Jev classifier that drive
    Z3 formal theorem proving and logical verification.
    """
    rule_id: str = Field(default_factory=lambda: "rule_1")
    raw_text: str
    domain: RuleDomain = RuleDomain.EXPENSE_POLICY
    scope: TargetScope = TargetScope.SINGLE_TRANSACTION
    category: SpendCategory = SpendCategory.GENERAL_SPEND
    operator: ComparisonOperator = ComparisonOperator.ALWAYS
    threshold_amount: Optional[float] = None
    upper_threshold_amount: Optional[float] = None
    currency: str = "USD"
    vendor_pattern: Optional[str] = None
    description_keywords: List[str] = Field(default_factory=list)
    action: RuleAction = RuleAction.REQUIRE_APPROVAL

    # Logical verification requirements (boolean predicates for Z3)
    requires_receipt: bool = False
    requires_manager_approval: bool = False
    requires_vp_approval: bool = False
    requires_purchase_order: bool = False
    requires_itemized_attendees: bool = False
    requires_w9: bool = False
    requires_compliance_audit: bool = False

    # QuickBooks accounting mappings & constraints
    target_department: Optional[str] = None
    qb_account: Optional[str] = None
    qb_class: Optional[str] = None
    enforce_debit_credit_balance: bool = False

    # Anti-split evasion window
    max_aggregate_amount: Optional[float] = None
    aggregate_window_hours: Optional[int] = None

    # Model confidence metrics from Jev calibration
    confidence_scores: Dict[str, float] = Field(default_factory=dict)


class Transaction(BaseModel):
    """
    An expense transaction or bill to verify against formal spend rules.
    """
    id: str = "tx_001"
    amount: float
    currency: str = "USD"
    category: SpendCategory = SpendCategory.GENERAL_SPEND
    vendor: str = "Unknown Vendor"
    description: str = ""
    department: str = "General"
    employee_id: str = "emp_001"
    attendee_count: int = 1
    has_receipt: bool = False
    approved_by_manager: bool = False
    approved_by_vp: bool = False
    has_purchase_order: bool = False
    has_itemized_attendees: bool = False
    has_w9: bool = False
    audit_cleared: bool = False
    qb_account: Optional[str] = None
    qb_class: Optional[str] = None
    timestamp: Optional[str] = None


class JournalLineItem(BaseModel):
    """
    A single line in a double-entry QuickBooks accounting journal entry.
    """
    account: str
    debit: float = 0.0
    credit: float = 0.0
    department_class: Optional[str] = None
    description: str = ""


class JournalEntry(BaseModel):
    """
    A QuickBooks general ledger journal entry.
    """
    id: str = "je_001"
    date: str = "2026-10-17"
    description: str = ""
    lines: List[JournalLineItem] = Field(default_factory=list)


class ProofStatus(str, Enum):
    PROVEN_COMPLIANT = "PROVEN_COMPLIANT"
    VIOLATION_DETECTED = "VIOLATION_DETECTED"
    INCONSISTENT_POLICY = "INCONSISTENT_POLICY"
    UNDETERMINED = "UNDETERMINED"


class ProofResult(BaseModel):
    """
    Formal verification output produced by the Z3 SMT solver.
    """
    status: ProofStatus
    is_valid: bool
    proof_type: str
    explanation: str
    rule_id: Optional[str] = None
    counterexample: Optional[Dict[str, Any]] = None
    z3_assertions: Optional[List[str]] = None
    solver_time_ms: float = 0.0

