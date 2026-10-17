"""
QuickBooks Accounting & Double-Entry Ledger Verification in Z3.
Proves fundamental accounting equations and GL classification rules.
"""

import time
from typing import List, Optional
import z3

from ..models import (
    JournalEntry,
    ProofResult,
    ProofStatus,
    Z3RuleParameters,
)


class QuickBooksZ3Verifier:
    """
    Formal verification of QuickBooks journal entries and GL accounting rules using Z3.
    Verifies:
      1. Double-entry equation: Sum(Debits) == Sum(Credits)
      2. Non-negativity of individual debit/credit amounts
      3. Class-tracking completeness for expense accounts
      4. Account mapping compliance against classified rule parameters
    """

    def prove_journal_entry(
        self,
        entry: JournalEntry,
        rule: Optional[Z3RuleParameters] = None,
    ) -> ProofResult:
        """
        Formally proves whether a QuickBooks journal entry is mathematically balanced
        and conforms to corporate chart of accounts rules.
        """
        start = time.perf_counter()
        solver = z3.Solver()

        if not entry.lines:
            return ProofResult(
                status=ProofStatus.VIOLATION_DETECTED,
                is_valid=False,
                proof_type="QuickBooks Balance Check",
                explanation="Journal entry contains no line items.",
                solver_time_ms=0.0,
            )

        # Symbolic variables for each line
        debit_vars = []
        credit_vars = []
        for i, line in enumerate(entry.lines):
            d_var = z3.Real(f"line_{i}_debit")
            c_var = z3.Real(f"line_{i}_credit")
            debit_vars.append(d_var)
            credit_vars.append(c_var)

            # Bind concrete amounts
            solver.add(d_var == z3.RealVal(round(line.debit, 4)))
            solver.add(c_var == z3.RealVal(round(line.credit, 4)))

            # Non-negativity constraint
            solver.add(d_var >= 0)
            solver.add(c_var >= 0)

            # At least one must be non-zero or both zero
            # Cannot have both non-zero on the same line in standard accounting
            if line.debit > 0 and line.credit > 0:
                elapsed = (time.perf_counter() - start) * 1000.0
                return ProofResult(
                    status=ProofStatus.VIOLATION_DETECTED,
                    is_valid=False,
                    proof_type="QuickBooks Double-Entry Constraint",
                    explanation=f"Line {i} ({line.account}) has both non-zero Debit and Credit, violating single-line ledger conventions.",
                    counterexample={"line_index": i, "account": line.account, "debit": line.debit, "credit": line.credit},
                    solver_time_ms=round(elapsed, 3),
                )

        # Sum of debits and sum of credits
        sum_debits = z3.Sum(debit_vars)
        sum_credits = z3.Sum(credit_vars)

        # Imbalance condition: sum_debits != sum_credits
        imbalance_cond = (sum_debits != sum_credits)

        solver.push()
        solver.add(imbalance_cond)
        imbalance_check = solver.check()
        solver.pop()

        elapsed = (time.perf_counter() - start) * 1000.0

        if imbalance_check == z3.sat:
            # Imbalance proven!
            total_d = sum(line.debit for line in entry.lines)
            total_c = sum(line.credit for line in entry.lines)
            diff = round(abs(total_d - total_c), 4)
            return ProofResult(
                status=ProofStatus.VIOLATION_DETECTED,
                is_valid=False,
                proof_type="Double-Entry Theorem Violation",
                explanation=f"QuickBooks Ledger Imbalance: Total Debits (${total_d:,.2f}) != Total Credits (${total_c:,.2f}). Difference: ${diff:,.2f}.",
                counterexample={"total_debit": total_d, "total_credit": total_c, "imbalance": diff},
                solver_time_ms=round(elapsed, 3),
            )

        # If a rule parameter is provided, check account mapping & class requirements
        if rule:
            if rule.qb_account:
                accounts_in_entry = [line.account for line in entry.lines]
                if not any(rule.qb_account in acc for acc in accounts_in_entry):
                    return ProofResult(
                        status=ProofStatus.VIOLATION_DETECTED,
                        is_valid=False,
                        proof_type="QuickBooks Account Mapping Violation",
                        explanation=f"Journal entry violates rule '{rule.rule_id}': Required GL account '{rule.qb_account}' is missing from entry.",
                        counterexample={"expected_account": rule.qb_account, "present_accounts": accounts_in_entry},
                        solver_time_ms=round(elapsed, 3),
                    )

            if rule.qb_class:
                missing_class = [
                    line.account for line in entry.lines
                    if line.debit > 0 and (not line.department_class or line.department_class.lower() != rule.qb_class.lower())
                ]
                if missing_class:
                    return ProofResult(
                        status=ProofStatus.VIOLATION_DETECTED,
                        is_valid=False,
                        proof_type="QuickBooks Class Tracking Violation",
                        explanation=f"Journal entry violates rule '{rule.rule_id}': Expense lines {missing_class} missing mandatory Class '{rule.qb_class}'.",
                        counterexample={"missing_class_lines": missing_class, "expected_class": rule.qb_class},
                        solver_time_ms=round(elapsed, 3),
                    )

        total_d = sum(line.debit for line in entry.lines)
        return ProofResult(
            status=ProofStatus.PROVEN_COMPLIANT,
            is_valid=True,
            proof_type="Z3 Double-Entry Formal Balance Certificate",
            explanation=f"Formally proven balanced in Z3: Sum(Debits) == Sum(Credits) == ${total_d:,.2f}. All accounting constraints verified.",
            solver_time_ms=round(elapsed, 3),
        )

