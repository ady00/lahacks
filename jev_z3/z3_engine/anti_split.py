"""
Anti-Split Transaction Circumvention Proof Engine in Z3.
Detects when multiple small transactions are structured to evade approval thresholds.
"""

import time
from typing import List, Optional
import z3

from ..models import (
    ProofResult,
    ProofStatus,
    Transaction,
    Z3RuleParameters,
)


class AntiSplitZ3Detector:
    """
    Formally verifies whether a set of transactions constitutes a split-structuring
    evasion tactic using Z3 subset-sum constraint solving.
    """

    def prove_anti_split(
        self,
        transactions: List[Transaction],
        rule: Z3RuleParameters,
        single_threshold: Optional[float] = None,
    ) -> ProofResult:
        """
        Formally proves if any subset of transactions circumvents single-transaction approval
        while exceeding the cumulative aggregate limit.
        """
        start = time.perf_counter()

        if not transactions:
            return ProofResult(
                status=ProofStatus.PROVEN_COMPLIANT,
                is_valid=True,
                proof_type="Anti-Split Proof",
                explanation="No transactions to evaluate.",
                solver_time_ms=0.0,
            )

        aggregate_limit = rule.max_aggregate_amount or rule.threshold_amount or 1000.0
        single_limit = single_threshold or (aggregate_limit * 0.9)  # default single approval threshold

        solver = z3.Solver()
        indicators = []
        tx_amounts = []

        for i, tx in enumerate(transactions):
            ind = z3.Bool(f"include_tx_{i}")
            indicators.append(ind)
            tx_amounts.append(tx.amount)

        # Objective: find a non-empty subset where each individual item is <= single_limit,
        # but the sum of selected items > aggregate_limit
        selected_terms = [
            z3.If(indicators[i], z3.RealVal(tx_amounts[i]), z3.RealVal(0.0))
            for i in range(len(transactions))
        ]
        total_sum = z3.Sum(selected_terms)

        # Condition 1: Total exceeds the aggregate limit
        solver.add(total_sum > z3.RealVal(aggregate_limit))

        # Condition 2: Each selected transaction is individually below or equal to the single threshold
        for i, amt in enumerate(tx_amounts):
            solver.add(z3.Implies(indicators[i], z3.RealVal(amt) <= z3.RealVal(single_limit)))

        # Condition 3: At least 2 transactions involved in the split
        num_selected = z3.Sum([z3.If(ind, 1, 0) for ind in indicators])
        solver.add(num_selected >= 2)

        check_res = solver.check()
        elapsed = (time.perf_counter() - start) * 1000.0

        if check_res == z3.sat:
            m = solver.model()
            evasion_indices = [
                i for i, ind in enumerate(indicators)
                if z3.is_true(m.eval(ind))
            ]
            evasion_txs = [transactions[i] for i in evasion_indices]
            evasion_total = sum(tx.amount for tx in evasion_txs)

            return ProofResult(
                status=ProofStatus.VIOLATION_DETECTED,
                is_valid=False,
                proof_type="SMT Split-Structuring Proof (Threshold Evasion Detected)",
                explanation=(
                    f"Circumvention Detected by Z3: {len(evasion_txs)} transactions individually bypass "
                    f"the single-transaction limit of ${single_limit:,.2f}, but cumulatively sum to "
                    f"${evasion_total:,.2f}, exceeding the maximum aggregate threshold of ${aggregate_limit:,.2f}."
                ),
                rule_id=rule.rule_id,
                counterexample={
                    "split_transaction_ids": [tx.id for tx in evasion_txs],
                    "individual_amounts": [tx.amount for tx in evasion_txs],
                    "cumulative_amount": evasion_total,
                    "aggregate_limit": aggregate_limit,
                    "single_threshold": single_limit,
                },
                solver_time_ms=round(elapsed, 3),
            )

        return ProofResult(
            status=ProofStatus.PROVEN_COMPLIANT,
            is_valid=True,
            proof_type="SMT Non-Evasion Certificate",
            explanation=f"Formally proven by Z3: No subset of transactions exceeds the ${aggregate_limit:,.2f} aggregate limit while evading individual approval.",
            rule_id=rule.rule_id,
            solver_time_ms=round(elapsed, 3),
        )

