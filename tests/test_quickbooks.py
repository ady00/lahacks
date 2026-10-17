"""
Tests for QuickBooks double-entry ledger verification and anti-split detection in Z3.
"""

import pytest
from jev_z3.jev.classifier import JevRuleClassifier
from jev_z3.models import (
    JournalEntry,
    JournalLineItem,
    ProofStatus,
    Transaction,
)
from jev_z3.z3_engine.accounting import QuickBooksZ3Verifier
from jev_z3.z3_engine.anti_split import AntiSplitZ3Detector


@pytest.fixture
def qb_verifier():
    return QuickBooksZ3Verifier()


@pytest.fixture
def split_detector():
    return AntiSplitZ3Detector()


def test_quickbooks_balanced_entry(qb_verifier):
    entry = JournalEntry(
        id="JE-101",
        description="Office Supplies Purchase",
        lines=[
            JournalLineItem(account="6100_office_supplies", debit=450.0, credit=0.0, department_class="Admin"),
            JournalLineItem(account="2000_accounts_payable", debit=0.0, credit=450.0),
        ],
    )
    result = qb_verifier.prove_journal_entry(entry)
    assert result.status == ProofStatus.PROVEN_COMPLIANT
    assert result.is_valid is True
    assert "Sum(Debits) == Sum(Credits)" in result.explanation


def test_quickbooks_imbalanced_entry(qb_verifier):
    entry = JournalEntry(
        id="JE-102",
        description="Imbalanced Invoice",
        lines=[
            JournalLineItem(account="6100_office_supplies", debit=500.0, credit=0.0),
            JournalLineItem(account="2000_accounts_payable", debit=0.0, credit=450.0),  # $50 off!
        ],
    )
    result = qb_verifier.prove_journal_entry(entry)
    assert result.status == ProofStatus.VIOLATION_DETECTED
    assert result.is_valid is False
    assert result.counterexample["imbalance"] == 50.0


def test_anti_split_evasion_detected(split_detector):
    classifier = JevRuleClassifier()
    rule_nl = "No employee may split transactions totaling over $1,000 to the same merchant within 24 hours to evade approval."
    params = classifier.classify_rule(rule_nl)

    # Three transactions: $400, $450, $250 = $1,100 (each <= $500 single limit)
    tx_batch = [
        Transaction(id="tx_1", amount=400.0, vendor="Amazon"),
        Transaction(id="tx_2", amount=450.0, vendor="Amazon"),
        Transaction(id="tx_3", amount=250.0, vendor="Amazon"),
    ]

    res = split_detector.prove_anti_split(tx_batch, params, single_threshold=500.0)
    assert res.status == ProofStatus.VIOLATION_DETECTED
    assert res.is_valid is False
    assert "Circumvention Detected" in res.explanation
    assert res.counterexample["cumulative_amount"] == 1100.0


def test_anti_split_legitimate_transactions(split_detector):
    classifier = JevRuleClassifier()
    rule_nl = "No employee may split transactions totaling over $1,000 to the same merchant within 24 hours."
    params = classifier.classify_rule(rule_nl)

    # Total $450 <= $1,000 limit
    tx_batch = [
        Transaction(id="tx_1", amount=200.0, vendor="Amazon"),
        Transaction(id="tx_2", amount=250.0, vendor="Amazon"),
    ]

    res = split_detector.prove_anti_split(tx_batch, params, single_threshold=500.0)
    assert res.status == ProofStatus.PROVEN_COMPLIANT
    assert res.is_valid is True

