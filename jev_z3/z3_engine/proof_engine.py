"""
Z3 Formal Proof and Verification Engine for Spend Rules and Accounting Business Logic.
Translates Jev-classified Z3RuleParameters into first-order SMT constraints.
"""

import time
from typing import Any, Dict, List, Optional, Tuple
import z3

from ..models import (
    ComparisonOperator,
    ProofResult,
    ProofStatus,
    RuleAction,
    RuleDomain,
    SpendCategory,
    TargetScope,
    Transaction,
    Z3RuleParameters,
)


class Z3SpendProofEngine:
    """
    Formal theorem prover and verification engine using Z3.
    Constructs first-order logic formulas for corporate spend policies,
    evaluates transaction compliance, detects rule contradictions, and generates proofs.
    """

    def __init__(self):
        pass

    def build_transaction_sorts(self, prefix: str = "tx") -> Dict[str, Any]:
        """
        Creates symbolic Z3 variables for a transaction.
        """
        return {
            "amount": z3.Real(f"{prefix}_amount"),
            "category": z3.String(f"{prefix}_category"),
            "vendor": z3.String(f"{prefix}_vendor"),
            "department": z3.String(f"{prefix}_department"),
            "employee_id": z3.String(f"{prefix}_employee_id"),
            "attendee_count": z3.Int(f"{prefix}_attendee_count"),
            "has_receipt": z3.Bool(f"{prefix}_has_receipt"),
            "approved_by_manager": z3.Bool(f"{prefix}_approved_by_manager"),
            "approved_by_vp": z3.Bool(f"{prefix}_approved_by_vp"),
            "has_purchase_order": z3.Bool(f"{prefix}_has_purchase_order"),
            "has_itemized_attendees": z3.Bool(f"{prefix}_has_itemized_attendees"),
            "has_w9": z3.Bool(f"{prefix}_has_w9"),
            "audit_cleared": z3.Bool(f"{prefix}_audit_cleared"),
            "qb_account": z3.String(f"{prefix}_qb_account"),
            "qb_class": z3.String(f"{prefix}_qb_class"),
        }

    def compile_antecedent(self, sym: Dict[str, Any], params: Z3RuleParameters) -> z3.BoolRef:
        """
        Builds the Antecedent A(T): condition under which the rule applies.
        """
        conds: List[z3.BoolRef] = []

        # Domain boundary: amount must be non-negative
        conds.append(sym["amount"] >= 0)

        # 1. Category filter
        if params.category != SpendCategory.GENERAL_SPEND and params.category != SpendCategory.ANY:
            conds.append(sym["category"] == z3.StringVal(params.category.value))

        # 2. Threshold comparison
        amt_expr = sym["amount"]
        if params.scope == TargetScope.PER_ATTENDEE:
            # Per attendee amount = total amount / attendee count
            amt_expr = sym["amount"] / z3.ToReal(z3.If(sym["attendee_count"] > 0, sym["attendee_count"], 1))

        if params.threshold_amount is not None:
            thresh = z3.RealVal(params.threshold_amount)
            if params.operator == ComparisonOperator.GREATER_THAN:
                conds.append(amt_expr > thresh)
            elif params.operator == ComparisonOperator.GREATER_EQUAL:
                conds.append(amt_expr >= thresh)
            elif params.operator == ComparisonOperator.LESS_THAN:
                conds.append(amt_expr < thresh)
            elif params.operator == ComparisonOperator.LESS_EQUAL:
                conds.append(amt_expr <= thresh)
            elif params.operator == ComparisonOperator.EQUALS:
                conds.append(amt_expr == thresh)
            elif params.operator == ComparisonOperator.BETWEEN and params.upper_threshold_amount is not None:
                conds.append(amt_expr >= thresh)
                conds.append(amt_expr <= z3.RealVal(params.upper_threshold_amount))

        # 3. Vendor filter
        if params.vendor_pattern:
            conds.append(sym["vendor"] == z3.StringVal(params.vendor_pattern))

        # 4. Department filter
        if params.target_department:
            conds.append(sym["department"] == z3.StringVal(params.target_department))

        if not conds:
            return z3.BoolVal(True)
        return z3.And(*conds)

    def compile_consequent(self, sym: Dict[str, Any], params: Z3RuleParameters) -> z3.BoolRef:
        """
        Builds the Consequent C(T): obligations mandated by the rule when triggered.
        """
        # If action is REJECT, this category/threshold is strictly prohibited
        if params.action == RuleAction.REJECT:
            return z3.BoolVal(False)

        reqs: List[z3.BoolRef] = []

        if params.requires_receipt:
            reqs.append(sym["has_receipt"] == z3.BoolVal(True))

        if params.requires_manager_approval:
            reqs.append(sym["approved_by_manager"] == z3.BoolVal(True))

        if params.requires_vp_approval:
            reqs.append(sym["approved_by_vp"] == z3.BoolVal(True))

        if params.requires_purchase_order:
            reqs.append(sym["has_purchase_order"] == z3.BoolVal(True))

        if params.requires_itemized_attendees:
            reqs.append(sym["has_itemized_attendees"] == z3.BoolVal(True))

        if params.requires_w9:
            reqs.append(sym["has_w9"] == z3.BoolVal(True))

        if params.requires_compliance_audit:
            reqs.append(sym["audit_cleared"] == z3.BoolVal(True))

        is_qb_rule = (
            params.domain == RuleDomain.QUICKBOOKS_ROUTING
            or params.action == RuleAction.ASSIGN_ACCOUNT
        )
        if is_qb_rule and params.qb_account:
            reqs.append(sym["qb_account"] == z3.StringVal(params.qb_account))

        if is_qb_rule and params.qb_class:
            reqs.append(sym["qb_class"] == z3.StringVal(params.qb_class))

        if not reqs:
            return z3.BoolVal(True)
        return z3.And(*reqs)

    def compile_rule_axiom(self, sym: Dict[str, Any], params: Z3RuleParameters) -> z3.BoolRef:
        """
        Encodes the universal policy axiom: Antecedent(T) => Consequent(T)
        """
        antecedent = self.compile_antecedent(sym, params)
        consequent = self.compile_consequent(sym, params)
        return z3.Implies(antecedent, consequent)

    def get_rule_formula_strings(self, params: Z3RuleParameters) -> Dict[str, str]:
        """
        Returns string and SMT-LIB2 representations of the compiled Z3 formulas.
        """
        sym = self.build_transaction_sorts("tx")
        a = self.compile_antecedent(sym, params)
        c = self.compile_consequent(sym, params)
        axiom = self.compile_rule_axiom(sym, params)
        return {
            "antecedent": str(a),
            "consequent": str(c),
            "axiom": str(axiom),
            "smt2": axiom.sexpr(),
        }

    def prove_compliance(self, tx: Transaction, params: Z3RuleParameters) -> ProofResult:
        """
        Formally proves whether a concrete transaction complies with the rule.
        Uses proof by contradiction:
        Attempts to satisfy (Antecedent(T) AND NOT Consequent(T)) under the concrete transaction constants.
        If UNSAT -> Mathematical proof of compliance!
        If SAT   -> Violation detected, counterexample extracted.
        """
        start = time.perf_counter()
        solver = z3.Solver()

        sym = self.build_transaction_sorts("tx")

        # Bind transaction concrete values to symbolic variables
        solver.add(sym["amount"] == z3.RealVal(tx.amount))
        solver.add(sym["category"] == z3.StringVal(tx.category.value))
        solver.add(sym["vendor"] == z3.StringVal(tx.vendor))
        solver.add(sym["department"] == z3.StringVal(tx.department))
        solver.add(sym["employee_id"] == z3.StringVal(tx.employee_id))
        solver.add(sym["attendee_count"] == z3.IntVal(tx.attendee_count))
        solver.add(sym["has_receipt"] == z3.BoolVal(tx.has_receipt))
        solver.add(sym["approved_by_manager"] == z3.BoolVal(tx.approved_by_manager))
        solver.add(sym["approved_by_vp"] == z3.BoolVal(tx.approved_by_vp))
        solver.add(sym["has_purchase_order"] == z3.BoolVal(tx.has_purchase_order))
        solver.add(sym["has_itemized_attendees"] == z3.BoolVal(tx.has_itemized_attendees))
        solver.add(sym["has_w9"] == z3.BoolVal(tx.has_w9))
        solver.add(sym["audit_cleared"] == z3.BoolVal(tx.audit_cleared))
        if tx.qb_account:
            solver.add(sym["qb_account"] == z3.StringVal(tx.qb_account))
        if tx.qb_class:
            solver.add(sym["qb_class"] == z3.StringVal(tx.qb_class))

        antecedent = self.compile_antecedent(sym, params)
        consequent = self.compile_consequent(sym, params)

        # Violation condition: Antecedent holds but Consequent is violated
        violation_cond = z3.And(antecedent, z3.Not(consequent))

        solver.push()
        solver.add(violation_cond)
        check_result = solver.check()
        elapsed = (time.perf_counter() - start) * 1000.0

        if check_result == z3.unsat:
            # Check if rule was triggered or vacuously satisfied
            solver.pop()
            solver.add(antecedent)
            triggered = (solver.check() == z3.sat)
            msg = (
                f"Formally proven compliant by Z3. Transaction triggers policy and satisfies all required constraints."
                if triggered else
                f"Formally proven compliant by Z3. Transaction amount/category falls outside trigger threshold."
            )
            return ProofResult(
                status=ProofStatus.PROVEN_COMPLIANT,
                is_valid=True,
                proof_type="SMT Unsatisfiability Certificate (No Violation Possible)",
                explanation=msg,
                rule_id=params.rule_id,
                z3_assertions=[str(a) for a in solver.assertions()],
                solver_time_ms=round(elapsed, 3),
            )

        elif check_result == z3.sat:
            m = solver.model()
            is_qb_rule = (
                params.domain == RuleDomain.QUICKBOOKS_ROUTING
                or params.action == RuleAction.ASSIGN_ACCOUNT
            )
            failed_reqs = []
            if params.requires_receipt and not tx.has_receipt:
                failed_reqs.append("Missing required itemized receipt")
            if params.requires_manager_approval and not tx.approved_by_manager:
                failed_reqs.append("Missing required manager approval")
            if params.requires_vp_approval and not tx.approved_by_vp:
                failed_reqs.append("Missing required VP/Executive approval")
            if params.requires_purchase_order and not tx.has_purchase_order:
                failed_reqs.append("Missing required purchase order (PO)")
            if params.requires_itemized_attendees and not tx.has_itemized_attendees:
                failed_reqs.append("Missing required attendee breakdown")
            if params.requires_w9 and not tx.has_w9:
                failed_reqs.append("Missing signed W-9 tax form")
            if params.requires_compliance_audit and not tx.audit_cleared:
                failed_reqs.append("Failed compliance/sanctions audit clearance")
            if params.action == RuleAction.REJECT:
                failed_reqs.append(f"Expense matches prohibited category/threshold ({params.raw_text})")
            if is_qb_rule and params.qb_account and tx.qb_account != params.qb_account:
                failed_reqs.append(f"Incorrect GL Account: expected {params.qb_account}, got {tx.qb_account}")

            return ProofResult(
                status=ProofStatus.VIOLATION_DETECTED,
                is_valid=False,
                proof_type="SMT Satisfying Violation Counterexample",
                explanation=f"Policy violation detected: {'; '.join(failed_reqs) if failed_reqs else 'Constraint obligation failed.'}",
                rule_id=params.rule_id,
                counterexample={
                    "transaction_id": tx.id,
                    "amount": tx.amount,
                    "category": tx.category.value,
                    "failed_requirements": failed_reqs,
                },
                z3_assertions=[str(a) for a in solver.assertions()],
                solver_time_ms=round(elapsed, 3),
            )

        else:
            return ProofResult(
                status=ProofStatus.UNDETERMINED,
                is_valid=False,
                proof_type="SMT Undetermined",
                explanation="Z3 solver timed out or returned unknown.",
                rule_id=params.rule_id,
                solver_time_ms=round(elapsed, 3),
            )

    def prove_policy_consistency(
        self,
        rule1: Z3RuleParameters,
        rule2: Z3RuleParameters,
    ) -> ProofResult:
        """
        Formally verifies whether two spend policies are logically consistent
        or contain mutual contradictions (e.g., overlapping triggers with conflicting requirements).
        """
        start = time.perf_counter()
        solver = z3.Solver()
        sym = self.build_transaction_sorts("tx")

        a1 = self.compile_antecedent(sym, rule1)
        c1 = self.compile_consequent(sym, rule1)

        a2 = self.compile_antecedent(sym, rule2)
        c2 = self.compile_consequent(sym, rule2)

        # Contradiction query:
        # Can a transaction trigger BOTH rules (A1 AND A2), but satisfy C1 while violating C2 (or vice versa)?
        # Or even worse: A1 and A2 hold, but (C1 and C2) is UNSAT (no valid state exists in the intersection)?
        intersection_trigger = z3.And(a1, a2)
        both_satisfied = z3.And(c1, c2)

        # 1. Does the trigger intersection exist?
        solver.push()
        solver.add(intersection_trigger)
        can_intersect = (solver.check() == z3.sat)
        solver.pop()

        if not can_intersect:
            elapsed = (time.perf_counter() - start) * 1000.0
            return ProofResult(
                status=ProofStatus.PROVEN_COMPLIANT,
                is_valid=True,
                proof_type="SMT Disjoint Policy Proof",
                explanation="The two policies have mutually exclusive activation domains (no possible conflict).",
                solver_time_ms=round(elapsed, 3),
            )

        # 2. In the intersection, is it possible to satisfy both rules simultaneously?
        solver.push()
        solver.add(intersection_trigger)
        solver.add(both_satisfied)
        sat_both = solver.check()
        solver.pop()

        elapsed = (time.perf_counter() - start) * 1000.0
        if sat_both == z3.unsat:
            return ProofResult(
                status=ProofStatus.INCONSISTENT_POLICY,
                is_valid=False,
                proof_type="SMT Contradiction Proof (Unsatisfiable Intersection)",
                explanation=f"Contradiction detected: Rules '{rule1.rule_id}' and '{rule2.rule_id}' define mutually incompatible requirements on overlapping transactions.",
                counterexample={
                    "rule1": rule1.raw_text,
                    "rule2": rule2.raw_text,
                    "conflict_type": "No transaction can satisfy both simultaneously",
                },
                solver_time_ms=round(elapsed, 3),
            )

        return ProofResult(
            status=ProofStatus.PROVEN_COMPLIANT,
            is_valid=True,
            proof_type="SMT Consistency Proof",
            explanation=f"Rules '{rule1.rule_id}' and '{rule2.rule_id}' are logically consistent and satisfiable in their overlapping domain.",
            solver_time_ms=round(elapsed, 3),
        )
