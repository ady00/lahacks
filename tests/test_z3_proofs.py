"""
Formal verification tests using Z3 SMT solver.
"""

import pytest
from jev_z3.jev.classifier import JevRuleClassifier
from jev_z3.models import (
    ProofStatus,
    SpendCategory,
    Transaction,
)
from jev_z3.z3_engine.proof_engine import Z3SpendProofEngine


@pytest.fixture
def classifier():
    return JevRuleClassifier()


@pytest.fixture
def proof_engine():
    return Z3SpendProofEngine()


def test_z3_prove_compliant_with_receipt(classifier, proof_engine):
    rule_nl = "Meals and entertainment expenses over $75 require an itemized receipt."
    params = classifier.classify_rule(rule_nl)

    tx_valid = Transaction(
        amount=120.0,
        category=SpendCategory.MEALS_ENTERTAINMENT,
        has_receipt=True,
    )

    result = proof_engine.prove_compliance(tx_valid, params)
    assert result.status == ProofStatus.PROVEN_COMPLIANT
    assert result.is_valid is True
    assert "Formally proven compliant" in result.explanation


def test_z3_prove_violation_missing_receipt(classifier, proof_engine):
    rule_nl = "Meals and entertainment expenses over $75 require an itemized receipt."
    params = classifier.classify_rule(rule_nl)

    tx_invalid = Transaction(
        amount=120.0,
        category=SpendCategory.MEALS_ENTERTAINMENT,
        has_receipt=False,
    )

    result = proof_engine.prove_compliance(tx_invalid, params)
    assert result.status == ProofStatus.VIOLATION_DETECTED
    assert result.is_valid is False
    assert result.counterexample is not None
    assert "Missing required itemized receipt" in result.counterexample["failed_requirements"]


def test_z3_prove_vacuously_compliant_below_threshold(classifier, proof_engine):
    rule_nl = "Meals and entertainment expenses over $75 require an itemized receipt."
    params = classifier.classify_rule(rule_nl)

    # $45 meal without receipt is permitted under policy
    tx_below = Transaction(
        amount=45.0,
        category=SpendCategory.MEALS_ENTERTAINMENT,
        has_receipt=False,
    )

    result = proof_engine.prove_compliance(tx_below, params)
    assert result.status == ProofStatus.PROVEN_COMPLIANT
    assert result.is_valid is True
    assert "outside trigger threshold" in result.explanation


def test_z3_prove_per_attendee_math(classifier, proof_engine):
    rule_nl = "Meals and dining exceeding $60 per attendee require an itemized attendees list."
    params = classifier.classify_rule(rule_nl)

    # $200 for 4 attendees = $50/person <= $60 -> compliant without attendees list
    tx_under_per_head = Transaction(
        amount=200.0,
        attendee_count=4,
        category=SpendCategory.MEALS_ENTERTAINMENT,
        has_itemized_attendees=False,
    )
    res_under = proof_engine.prove_compliance(tx_under_per_head, params)
    assert res_under.status == ProofStatus.PROVEN_COMPLIANT

    # $280 for 4 attendees = $70/person > $60 -> requires attendees list
    tx_over_per_head = Transaction(
        amount=280.0,
        attendee_count=4,
        category=SpendCategory.MEALS_ENTERTAINMENT,
        has_itemized_attendees=False,
    )
    res_over = proof_engine.prove_compliance(tx_over_per_head, params)
    assert res_over.status == ProofStatus.VIOLATION_DETECTED


def test_z3_detect_contradictory_policies(classifier, proof_engine):
    r1 = "All hardware equipment purchases over $1000 are strictly prohibited and rejected."
    r2 = "All hardware equipment purchases over $1000 require purchase order and manager approval."

    p1 = classifier.classify_rule(r1, rule_id="RULE_A")
    p2 = classifier.classify_rule(r2, rule_id="RULE_B")

    conflict_res = proof_engine.prove_policy_consistency(p1, p2)
    assert conflict_res.status == ProofStatus.INCONSISTENT_POLICY
    assert conflict_res.is_valid is False
    assert "Contradiction detected" in conflict_res.explanation

