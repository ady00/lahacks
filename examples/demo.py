#!/usr/bin/env python3
"""
Interactive demonstration of Jev-Z3:
Natural Language Accounting & Spend Rules to Formal Z3 Proofs.
"""

import json
from jev_z3 import JevRuleClassifier, Z3SpendProofEngine, Transaction, SpendCategory

def main():
    print("=" * 70)
    print("  JEV-Z3: Natural Language Spend Classifier & Z3 Formal Verification")
    print("=" * 70)

    classifier = JevRuleClassifier()
    prover = Z3SpendProofEngine()

    rule_text = "Software and SaaS subscriptions exceeding $500 per month must be billed to Engineering and approved by a VP."
    print(f"\n[1] Input Natural Language Spend Policy:\n    \"{rule_text}\"")

    # Step 1: Jev Classification
    params = classifier.classify_rule(rule_text, rule_id="RULE_SAAS_VP")
    print(f"\n[2] Jev 'System One' Extracted Z3 Parameters:")
    print(f"    • Domain:              {params.domain.value}")
    print(f"    • Scope:               {params.scope.value}")
    print(f"    • Spend Category:      {params.category.value}")
    print(f"    • Mathematical Op:     {params.operator.value} ${params.threshold_amount:,.2f}")
    print(f"    • Requires VP Signoff: {params.requires_vp_approval}")
    print(f"    • Target Department:   {params.target_department}")

    # Step 2: Evaluation on Transactions
    tx_unapproved = Transaction(
        id="TX-5501",
        amount=650.0,
        category=SpendCategory.SOFTWARE_SAAS,
        department="engineering",
        approved_by_manager=True,
        approved_by_vp=False,
    )
    print(f"\n[3] Evaluating Transaction 1:")
    print(f"    Amount: $650.00, Category: Software, VP Approved: False")
    res1 = prover.prove_compliance(tx_unapproved, params)
    print(f"    ==> Z3 Verdict: {res1.status.value}")
    print(f"        {res1.explanation}")

    tx_approved = Transaction(
        id="TX-5502",
        amount=650.0,
        category=SpendCategory.SOFTWARE_SAAS,
        department="engineering",
        approved_by_manager=True,
        approved_by_vp=True,
    )
    print(f"\n[4] Evaluating Transaction 2:")
    print(f"    Amount: $650.00, Category: Software, VP Approved: True")
    res2 = prover.prove_compliance(tx_approved, params)
    print(f"    ==> Z3 Verdict: {res2.status.value}")
    print(f"        {res2.explanation}")
    print(f"        Solver Execution Time: {res2.solver_time_ms} ms")

    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()

