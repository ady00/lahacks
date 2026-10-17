"""
Command-Line Interface (CLI) for Jev-Z3 Spend Rule Classifier & Formal Proof Engine.
"""

import argparse
import json
import sys
from typing import Any, Dict

from .jev.classifier import JevRuleClassifier
from .jev.query_parser import QueryParser
from .models import (
    JournalEntry,
    JournalLineItem,
    SpendCategory,
    Transaction,
)
from .rule_store import PolicyStore
from .z3_engine.accounting import QuickBooksZ3Verifier
from .z3_engine.anti_split import AntiSplitZ3Detector
from .z3_engine.preflight import PreflightVerdict, Z3PreflightEngine
from .z3_engine.proof_engine import Z3SpendProofEngine


def format_json(obj: Any) -> str:
    if hasattr(obj, "model_dump"):
        return json.dumps(obj.model_dump(), indent=2)
    return json.dumps(obj, indent=2)


def cmd_add_rule(args: argparse.Namespace) -> None:
    store = PolicyStore()
    rule_param, conflict_res = store.add_rule(args.rule_text, rule_id=args.rule_id)

    if conflict_res:
        print("\n❌ RULE REJECTED DUE TO POLICY CONFLICT IN Z3!")
        print(f"Status:      {conflict_res.status.value}")
        print(f"Explanation: {conflict_res.explanation}")
        if conflict_res.counterexample:
            print("Conflict details:")
            print(format_json(conflict_res.counterexample))
        sys.exit(1)

    print("\n✅ Natural Language Rule Successfully Verified & Added to Policy Store!")
    print(f"Rule ID:     {rule_param.rule_id}")
    print(f"Domain:      {rule_param.domain.value}")
    print(f"Category:    {rule_param.category.value}")
    print(f"Condition:   {rule_param.operator.value} ${rule_param.threshold_amount or 0:,.2f}")
    print(f"Requirements: Receipt={rule_param.requires_receipt}, Manager={rule_param.requires_manager_approval}, VP={rule_param.requires_vp_approval}, PO={rule_param.requires_purchase_order}")
    print(f"Total Active Rules in Store: {len(store.list_rules())}")


def cmd_list_rules(args: argparse.Namespace) -> None:
    store = PolicyStore()
    engine = Z3SpendProofEngine()
    rules = store.list_rules()
    print(f"\n=== Active Corporate Spend & Accounting Policies ({len(rules)} Rules) ===")
    for i, r in enumerate(rules, 1):
        thresh_str = f"{r.operator.value} ${r.threshold_amount:,.2f}" if r.threshold_amount is not None else "Always"
        print(f"\n[{r.rule_id}] \"{r.raw_text}\"")
        print(f"   Category: {r.category.value} | Condition: {thresh_str} | Scope: {r.scope.value}")
        reqs = []
        if r.requires_receipt:
            reqs.append("Receipt")
        if r.requires_manager_approval:
            reqs.append("Manager Approval")
        if r.requires_vp_approval:
            reqs.append("VP Approval")
        if r.requires_purchase_order:
            reqs.append("Purchase Order")
        if r.requires_itemized_attendees:
            reqs.append("Attendees List")
        if r.requires_w9:
            reqs.append("W-9 Form")
        print(f"   Requirements: {', '.join(reqs) if reqs else 'None (Unconditional)'}")

        if getattr(args, "show_z3", False):
            f = engine.get_rule_formula_strings(r)
            print(f"   📐 Z3 Antecedent A(T):  {f['antecedent']}")
            print(f"   📐 Z3 Consequent C(T):  {f['consequent']}")
            print(f"   ⚡ Z3 Policy Axiom:     {f['axiom']}")
            if getattr(args, "show_smt2", False):
                print(f"   📜 SMT-LIB2 Formula:\n      {f['smt2']}")


def cmd_show_rule(args: argparse.Namespace) -> None:
    store = PolicyStore()
    engine = Z3SpendProofEngine()
    rules = store.list_rules()

    target = next((r for r in rules if r.rule_id.lower() == args.rule_id.lower()), None)
    if not target:
        print(f"\n❌ Rule '{args.rule_id}' not found in active policy store.")
        print(f"Available Rule IDs: {', '.join(r.rule_id for r in rules)}")
        sys.exit(1)

    formulas = engine.get_rule_formula_strings(target)

    print("\n" + "=" * 65)
    print(f" RULE INSPECTOR: {target.rule_id}")
    print("=" * 65)
    print(f"Natural Language Policy:\n  \"{target.raw_text}\"")
    print(f"\n[1] Extracted Parameters:")
    print(f"    • Domain:              {target.domain.value}")
    print(f"    • Scope:               {target.scope.value}")
    print(f"    • Spend Category:      {target.category.value}")
    print(f"    • Mathematical Op:     {target.operator.value} ${target.threshold_amount or 0:,.2f}")
    print(f"    • Requires Receipt:    {target.requires_receipt}")
    print(f"    • Requires Manager:    {target.requires_manager_approval}")
    print(f"    • Requires VP:         {target.requires_vp_approval}")
    print(f"    • Requires PO / W-9:   PO={target.requires_purchase_order}, W9={target.requires_w9}")
    print(f"    • Target Department:   {target.target_department or 'Any'}")
    print(f"    • QB GL Account:       {target.qb_account or 'None'}")

    print(f"\n[2] Compiled Z3 First-Order Logic Formulas:")
    print(f"    • Antecedent A(T) [Trigger Condition]:")
    print(f"        {formulas['antecedent']}")
    print(f"    • Consequent C(T) [Required Obligations]:")
    print(f"        {formulas['consequent']}")
    print(f"    • Universal Policy Axiom (A => C):")
    print(f"        {formulas['axiom']}")

    if args.smt2:
        print(f"\n[3] SMT-LIB2 Benchmark Encoding (Z3 Solver Input):")
        print(f"    {formulas['smt2']}")
    print("=" * 65 + "\n")


def cmd_query(args: argparse.Namespace) -> None:
    parser = QueryParser()
    preflight = Z3PreflightEngine()
    store = PolicyStore()

    intent = parser.parse_query(args.query_text)
    rules = store.list_rules()

    print("\n" + "=" * 65)
    print(" PRE-PURCHASE SPEND CHECK (JEV + Z3 FORMAL ENGINE)")
    print("=" * 65)
    print(f"Client Query: \"{args.query_text}\"")
    print(f"\n[1] Extracted Purchase Intent:")
    print(f"    • Amount:          ${intent.amount:,.2f}")
    print(f"    • Category:        {intent.category.value}")
    print(f"    • Vendor:          {intent.vendor}")
    print(f"    • Department:      {intent.department}")
    print(f"    • Headcount:       {intent.attendee_count} person(s)")

    result = preflight.evaluate_query(intent, rules)

    print(f"\n[2] Z3 Preflight Verdict:")
    if result.verdict == PreflightVerdict.AUTO_APPROVED:
        print("    🟢 AUTO-APPROVED (Clear to swipe corporate card)")
    elif result.verdict == PreflightVerdict.CONDITIONALLY_APPROVED:
        print("    🟡 CONDITIONALLY APPROVED (Action required before/after swiping)")
    else:
        print("    🔴 BLOCKED (Prohibited by company policy)")

    print(f"\n[3] Policy Explanation:")
    print(f"    {result.summary}")

    if result.required_actions:
        print(f"\n[4] Required Checklist for Employee:")
        for idx, act in enumerate(result.required_actions, 1):
            print(f"    {idx}. {act}")

    if result.qb_routing.get("account"):
        print(f"\n[5] Automated QuickBooks Routing:")
        print(f"    • Account: {result.qb_routing.get('account')}")
        print(f"    • Class:   {result.qb_routing.get('class')}")

    print(f"\n[6] Formal Verification Metrics:")
    print(f"    • Active Rules Evaluated: {len(rules)}")
    print(f"    • Triggered Rule IDs:     {', '.join(result.triggered_rules) if result.triggered_rules else 'None'}")
    print(f"    • Z3 Solver Time:         {result.solver_time_ms} ms")
    print("=" * 65 + "\n")


def cmd_parse(args: argparse.Namespace) -> None:
    classifier = JevRuleClassifier()
    params = classifier.classify_rule(args.rule_text)
    print("\n=== Jev 'System One' Classification Result ===")
    print(format_json(params))


def cmd_prove(args: argparse.Namespace) -> None:
    classifier = JevRuleClassifier()
    engine = Z3SpendProofEngine()

    params = classifier.classify_rule(args.rule_text)
    print(f"\n[1] Jev Parsed Rule: {params.domain.value} | {params.category.value} {params.operator.value} ${params.threshold_amount or 0}")

    # Build transaction
    if args.tx_json:
        with open(args.tx_json, "r") as f:
            data = json.load(f)
            tx = Transaction(**data)
    else:
        tx = Transaction(
            id=args.tx_id or "tx_cli",
            amount=args.amount,
            category=SpendCategory(args.category) if args.category else params.category,
            vendor=args.vendor or "Test Vendor",
            department=args.department or "Engineering",
            has_receipt=args.has_receipt,
            approved_by_manager=args.approved_by_manager,
            approved_by_vp=args.approved_by_vp,
            has_purchase_order=args.has_po,
            has_w9=args.has_w9,
        )

    print(f"[2] Transaction: Amount=${tx.amount:,.2f}, Category={tx.category.value}, Receipt={tx.has_receipt}, VP Approval={tx.approved_by_vp}")
    print("[3] Invoking Z3 SMT Theorem Prover...")

    result = engine.prove_compliance(tx, params)
    print("\n=== Z3 Formal Verification Certificate ===")
    print(f"Status:        {result.status.value}")
    print(f"Valid:         {result.is_valid}")
    print(f"Proof Type:    {result.proof_type}")
    print(f"Explanation:   {result.explanation}")
    print(f"Solver Time:   {result.solver_time_ms} ms")

    if result.counterexample:
        print("\n--- Counterexample Details ---")
        print(format_json(result.counterexample))


def cmd_conflict(args: argparse.Namespace) -> None:
    classifier = JevRuleClassifier()
    engine = Z3SpendProofEngine()

    rule1 = classifier.classify_rule(args.rule1, rule_id="rule_A")
    rule2 = classifier.classify_rule(args.rule2, rule_id="rule_B")

    print("\n=== Analyzing Policy Consistency with Z3 ===")
    print(f"Rule A: {args.rule1}")
    print(f"Rule B: {args.rule2}\n")

    result = engine.prove_policy_consistency(rule1, rule2)
    print(f"Status:      {result.status.value}")
    print(f"Consistent:  {result.is_valid}")
    print(f"Proof Type:  {result.proof_type}")
    print(f"Explanation: {result.explanation}")
    print(f"Solver Time: {result.solver_time_ms} ms")


def cmd_ledger(args: argparse.Namespace) -> None:
    verifier = QuickBooksZ3Verifier()
    with open(args.entry_json, "r") as f:
        data = json.load(f)
        entry = JournalEntry(**data)

    print(f"\nVerifying QuickBooks Journal Entry: {entry.id} ({entry.description})")
    result = verifier.prove_journal_entry(entry)
    print(f"Status:      {result.status.value}")
    print(f"Balanced:    {result.is_valid}")
    print(f"Explanation: {result.explanation}")
    print(f"Solver Time: {result.solver_time_ms} ms")


def cmd_demo(args: argparse.Namespace) -> None:
    print("\n" + "=" * 65)
    print(" JEV-Z3: SPEND RULE CLASSIFIER & FORMAL PROOF DEMONSTRATION")
    print("=" * 65)

    classifier = JevRuleClassifier()
    engine = Z3SpendProofEngine()

    # Case 1: Software spend requiring VP approval
    rule_nl_1 = "Software and SaaS subscriptions exceeding $500 per month must be billed to Engineering and approved by a VP."
    print(f"\n[Case 1] Natural Language Policy:\n  \"{rule_nl_1}\"")

    params_1 = classifier.classify_rule(rule_nl_1, rule_id="POLICY_SAAS_VP")
    print(f"\n  Jev Classification Parameters:")
    print(f"    - Domain:             {params_1.domain.value}")
    print(f"    - Scope:              {params_1.scope.value}")
    print(f"    - Category:           {params_1.category.value}")
    print(f"    - Condition:          {params_1.operator.value} ${params_1.threshold_amount:,.2f}")
    print(f"    - Requires VP:        {params_1.requires_vp_approval}")
    print(f"    - Target Department:  {params_1.target_department}")

    # Subcase 1A: Non-compliant transaction (Amount $650, no VP approval)
    tx_fail = Transaction(
        id="tx_saas_01",
        amount=650.0,
        category=SpendCategory.SOFTWARE_SAAS,
        department="engineering",
        approved_by_manager=True,
        approved_by_vp=False,
    )
    res_fail = engine.prove_compliance(tx_fail, params_1)
    print(f"\n  Transaction ($650 SaaS, Manager Approved=True, VP Approved=False):")
    print(f"    -> Z3 Result:      {res_fail.status.value} (Violation Detected)")
    print(f"    -> Z3 Explanation: {res_fail.explanation}")

    # Subcase 1B: Compliant transaction (Amount $650, VP Approved)
    tx_pass = Transaction(
        id="tx_saas_02",
        amount=650.0,
        category=SpendCategory.SOFTWARE_SAAS,
        department="engineering",
        approved_by_manager=True,
        approved_by_vp=True,
    )
    res_pass = engine.prove_compliance(tx_pass, params_1)
    print(f"\n  Transaction ($650 SaaS, Manager Approved=True, VP Approved=True):")
    print(f"    -> Z3 Result:      {res_pass.status.value} (Mathematical Proof of Compliance)")
    print(f"    -> Z3 Time:        {res_pass.solver_time_ms} ms")

    # Case 2: Per-Attendee Dining Policy
    rule_nl_2 = "Meals and entertainment expenses over $75 per attendee require an itemized receipt and attendee headcount list."
    print(f"\n" + "-" * 65)
    print(f"[Case 2] Per-Attendee Dining Policy:\n  \"{rule_nl_2}\"")
    params_2 = classifier.classify_rule(rule_nl_2, rule_id="POLICY_MEALS_ATTENDEES")
    print(f"    - Scope:               {params_2.scope.value}")
    print(f"    - Requires Receipt:    {params_2.requires_receipt}")
    print(f"    - Requires Attendees:  {params_2.requires_itemized_attendees}")

    tx_dinner = Transaction(
        id="tx_dinner_01",
        amount=280.0,
        attendee_count=4,  # $70 per attendee (< $75 threshold!)
        category=SpendCategory.MEALS_ENTERTAINMENT,
        has_receipt=False,
        has_itemized_attendees=False,
    )
    res_dinner = engine.prove_compliance(tx_dinner, params_2)
    print(f"\n  Dinner: Total $280 for 4 attendees ($70/head <= $75 threshold):")
    print(f"    -> Z3 Result:      {res_dinner.status.value} ({res_dinner.explanation})")

    # Case 3: Policy Conflict Detection
    print(f"\n" + "-" * 65)
    print("[Case 3] Formal Policy Contradiction Verification in Z3")
    r_a = "All hardware equipment purchases over $1000 are strictly prohibited and rejected."
    r_b = "All hardware equipment purchases over $1000 require purchase order and manager approval."
    print(f"  Rule A: \"{r_a}\"")
    print(f"  Rule B: \"{r_b}\"")
    pa = classifier.classify_rule(r_a, rule_id="RULE_A")
    pb = classifier.classify_rule(r_b, rule_id="RULE_B")
    res_conflict = engine.prove_policy_consistency(pa, pb)
    print(f"    -> Z3 Proof:       {res_conflict.status.value}")
    print(f"    -> Z3 Explanation: {res_conflict.explanation}")

    # Case 4: Anti-Split Evasion Detection
    print(f"\n" + "-" * 65)
    print("[Case 4] Anti-Split Circumvention Detection in Z3")
    split_rule_nl = "No employee may submit multiple expenses totaling more than $1,000 to the same merchant within 24 hours to evade approval."
    split_params = classifier.classify_rule(split_rule_nl, rule_id="RULE_ANTI_SPLIT")
    detector = AntiSplitZ3Detector()

    # Three transactions of $400, $450, $250 = $1,100 (each <= $500 single limit)
    tx_batch = [
        Transaction(id="tx_1", amount=400.0, vendor="Amazon"),
        Transaction(id="tx_2", amount=450.0, vendor="Amazon"),
        Transaction(id="tx_3", amount=250.0, vendor="Amazon"),
    ]
    res_split = detector.prove_anti_split(tx_batch, split_params, single_threshold=500.0)
    print(f"  Batch: [tx_1: $400, tx_2: $450, tx_3: $250] to Amazon")
    print(f"    -> Z3 Result:      {res_split.status.value}")
    print(f"    -> Z3 Explanation: {res_split.explanation}")

    # Case 5: QuickBooks Ledger Balancing
    print(f"\n" + "-" * 65)
    print("[Case 5] QuickBooks Double-Entry Accounting Proof in Z3")
    verifier = QuickBooksZ3Verifier()
    entry = JournalEntry(
        id="JE-1002",
        description="Software SaaS Monthly Payment",
        lines=[
            JournalLineItem(account="6300_software_saas", debit=1200.0, credit=0.0, department_class="Engineering"),
            JournalLineItem(account="2000_accounts_payable", debit=0.0, credit=1200.0),
        ],
    )
    res_ledger = verifier.prove_journal_entry(entry, params_1)
    print(f"  Journal Entry: Debit $1,200 to 6300_software_saas (Class: Engineering), Credit $1,200 to 2000_accounts_payable")
    print(f"    -> Z3 Result:      {res_ledger.status.value}")
    print(f"    -> Z3 Proof:       {res_ledger.proof_type}")
    print(f"    -> Z3 Explanation: {res_ledger.explanation}")
    print("=" * 65 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Jev-Z3: Natural language accounting rule classifier to Z3 proofs")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # Subcommand: add-rule
    p_add_rule = subparsers.add_parser("add-rule", help="Add a natural language policy or QuickBooks rule to the policy store")
    p_add_rule.add_argument("rule_text", help="The natural language rule text to classify and add")
    p_add_rule.add_argument("--id", dest="rule_id", default=None, help="Custom Rule ID (e.g. POL-009)")
    p_add_rule.set_defaults(func=cmd_add_rule)

    # Subcommand: list-rules
    p_list_rules = subparsers.add_parser("list-rules", help="List all active spend policies in the policy store")
    p_list_rules.add_argument("--z3", dest="show_z3", action="store_true", help="Display compiled Z3 first-order logic formulas for each rule")
    p_list_rules.add_argument("--smt2", dest="show_smt2", action="store_true", help="Display SMT-LIB2 benchmark formulas")
    p_list_rules.set_defaults(func=cmd_list_rules)

    # Subcommand: show-rule
    p_show_rule = subparsers.add_parser("show-rule", help="Inspect a specific rule and its compiled Z3 formula")
    p_show_rule.add_argument("rule_id", help="Rule ID to inspect (e.g. POL-001)")
    p_show_rule.add_argument("--smt2", action="store_true", help="Display SMT-LIB2 benchmark formula")
    p_show_rule.set_defaults(func=cmd_show_rule)

    # Subcommand: query
    p_query = subparsers.add_parser("query", help="Ask a natural language purchase query (e.g. 'Can I buy a $650 Datadog monitoring subscription?')")
    p_query.add_argument("query_text", help="Client's purchase intent or question")
    p_query.set_defaults(func=cmd_query)

    # Subcommand: parse
    p_parse = subparsers.add_parser("parse", help="Parse natural language rule into Z3 parameters")
    p_parse.add_argument("rule_text", help="The natural language policy or QuickBooks rule")
    p_parse.set_defaults(func=cmd_parse)

    # Subcommand: prove
    p_prove = subparsers.add_parser("prove", help="Formally prove transaction compliance against a rule")
    p_prove.add_argument("--rule", dest="rule_text", required=True, help="Natural language policy rule")
    p_prove.add_argument("--amount", type=float, default=100.0, help="Transaction amount")
    p_prove.add_argument("--category", default=None, help="Expense category")
    p_prove.add_argument("--vendor", default="Vendor", help="Vendor name")
    p_prove.add_argument("--department", default="Engineering", help="Department")
    p_prove.add_argument("--tx-id", default="tx_01", help="Transaction ID")
    p_prove.add_argument("--has-receipt", action="store_true", help="Receipt attached")
    p_prove.add_argument("--approved-by-manager", action="store_true", help="Manager approved")
    p_prove.add_argument("--approved-by-vp", action="store_true", help="VP approved")
    p_prove.add_argument("--has-po", action="store_true", help="Purchase order attached")
    p_prove.add_argument("--has-w9", action="store_true", help="W9 on file")
    p_prove.add_argument("--tx-json", default=None, help="Path to transaction JSON file")
    p_prove.set_defaults(func=cmd_prove)

    # Subcommand: check-conflict
    p_conflict = subparsers.add_parser("check-conflict", help="Check if two rules are contradictory in Z3")
    p_conflict.add_argument("--rule1", required=True, help="First policy rule")
    p_conflict.add_argument("--rule2", required=True, help="Second policy rule")
    p_conflict.set_defaults(func=cmd_conflict)

    # Subcommand: verify-ledger
    p_ledger = subparsers.add_parser("verify-ledger", help="Formally prove balance of a QuickBooks journal entry")
    p_ledger.add_argument("--entry", dest="entry_json", required=True, help="Path to journal entry JSON file")
    p_ledger.set_defaults(func=cmd_ledger)

    # Subcommand: demo
    p_demo = subparsers.add_parser("demo", help="Run full demonstration of Jev classification and Z3 proofs")
    p_demo.set_defaults(func=cmd_demo)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
