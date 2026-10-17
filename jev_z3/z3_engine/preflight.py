"""
Preflight spend check and query resolution engine using Z3.
Evaluates purchase intents against active policies to solve for required approvals.
"""

from enum import Enum
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import z3

from ..models import (
    ComparisonOperator,
    RuleAction,
    SpendCategory,
    TargetScope,
    Transaction,
    Z3RuleParameters,
)
from ..jev.query_parser import PurchaseIntent
from .proof_engine import Z3SpendProofEngine


class PreflightVerdict(str, Enum):
    AUTO_APPROVED = "AUTO_APPROVED"
    CONDITIONALLY_APPROVED = "CONDITIONALLY_APPROVED"
    BLOCKED = "BLOCKED"


class PreflightResult(BaseModel):
    """
    Result of evaluating a client's natural language purchase query against the rulebook.
    """
    verdict: PreflightVerdict
    summary: str
    intent: PurchaseIntent
    triggered_rules: List[str] = Field(default_factory=list)
    required_actions: List[str] = Field(default_factory=list)
    qb_routing: Dict[str, Optional[str]] = Field(default_factory=dict)
    solver_time_ms: float = 0.0


class Z3PreflightEngine:
    """
    Evaluates client purchase intents against the full policy book using Z3.
    """

    def __init__(self):
        self.prover = Z3SpendProofEngine()

    def evaluate_query(
        self,
        intent: PurchaseIntent,
        rules: List[Z3RuleParameters],
    ) -> PreflightResult:
        """
        Determines whether a client can make a purchase and solves for necessary conditions.
        """
        start = time.perf_counter()

        triggered_rules: List[str] = []
        required_actions: List[str] = []
        blocked = False
        block_reasons: List[str] = []

        qb_account: Optional[str] = None
        qb_class: Optional[str] = None

        # Flags to check
        req_receipt = False
        req_manager = False
        req_vp = False
        req_po = False
        req_attendees = False
        req_w9 = False
        req_audit = False

        sym = self.prover.build_transaction_sorts("intent")

        for rule in rules:
            solver = z3.Solver()
            # Bind intent constants
            solver.add(sym["amount"] == z3.RealVal(intent.amount))
            solver.add(sym["category"] == z3.StringVal(intent.category.value))
            solver.add(sym["vendor"] == z3.StringVal(intent.vendor))
            solver.add(sym["department"] == z3.StringVal(intent.department.lower()))
            solver.add(sym["attendee_count"] == z3.IntVal(intent.attendee_count))

            antecedent = self.prover.compile_antecedent(sym, rule)
            solver.add(antecedent)

            # Check if this rule is triggered
            if solver.check() == z3.sat:
                triggered_rules.append(rule.rule_id)

                if rule.action == RuleAction.REJECT:
                    blocked = True
                    block_reasons.append(f"Prohibited by policy ({rule.raw_text})")

                if rule.requires_vp_approval:
                    req_vp = True
                if rule.requires_manager_approval:
                    req_manager = True
                if rule.requires_receipt:
                    req_receipt = True
                if rule.requires_purchase_order:
                    req_po = True
                if rule.requires_itemized_attendees:
                    req_attendees = True
                if rule.requires_w9:
                    req_w9 = True
                if rule.requires_compliance_audit:
                    req_audit = True

                if rule.qb_account:
                    qb_account = rule.qb_account
                if rule.qb_class:
                    qb_class = rule.qb_class

        # Build human-readable checklist of required actions
        if req_vp:
            required_actions.append("VP / Executive approval required before purchasing")
        elif req_manager:
            required_actions.append("Direct manager approval required")

        if req_po:
            required_actions.append("Purchase Order (PO) matching required via procurement")
        if req_w9:
            required_actions.append("Active W-9 tax form required on file for vendor")
        if req_receipt:
            required_actions.append("Itemized receipt must be uploaded after payment")
        if req_attendees:
            required_actions.append(f"Attendee names and headcount list required ({intent.attendee_count} people)")
        if req_audit:
            required_actions.append("Compliance audit review required")

        elapsed = (time.perf_counter() - start) * 1000.0

        if blocked:
            verdict = PreflightVerdict.BLOCKED
            summary = f"Purchase is BLOCKED by policy: {'; '.join(block_reasons)}"
        elif required_actions:
            verdict = PreflightVerdict.CONDITIONALLY_APPROVED
            summary = f"Purchase is PERMITTED with {len(required_actions)} requirement(s) satisfied."
        else:
            verdict = PreflightVerdict.AUTO_APPROVED
            summary = "Purchase is AUTO-APPROVED. You may swipe your corporate card immediately; no prior approvals needed."

        return PreflightResult(
            verdict=verdict,
            summary=summary,
            intent=intent,
            triggered_rules=triggered_rules,
            required_actions=required_actions,
            qb_routing={
                "account": qb_account,
                "class": qb_class or intent.department,
            },
            solver_time_ms=round(elapsed, 3),
        )

