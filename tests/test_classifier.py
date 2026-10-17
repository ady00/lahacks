"""
Unit tests for Jev-based natural language rule classification.
"""

import pytest
from jev_z3.jev.classifier import JevRuleClassifier
from jev_z3.models import (
    ComparisonOperator,
    RuleDomain,
    SpendCategory,
    TargetScope,
)


@pytest.fixture
def classifier():
    return JevRuleClassifier()


def test_classify_meals_policy(classifier):
    rule = "Meals and entertainment expenses over $75 require an itemized receipt and manager approval."
    params = classifier.classify_rule(rule)

    assert params.domain == RuleDomain.EXPENSE_POLICY
    assert params.category == SpendCategory.MEALS_ENTERTAINMENT
    assert params.operator == ComparisonOperator.GREATER_THAN
    assert params.threshold_amount == 75.0
    assert params.requires_receipt is True
    assert params.requires_manager_approval is True
    assert params.requires_vp_approval is False


def test_classify_saas_vp_approval(classifier):
    rule = "Software and SaaS subscriptions exceeding $500 per month must be billed to Engineering and approved by a VP."
    params = classifier.classify_rule(rule)

    assert params.domain == RuleDomain.EXPENSE_POLICY
    assert params.scope == TargetScope.MONTHLY_RECURRING
    assert params.category == SpendCategory.SOFTWARE_SAAS
    assert params.operator == ComparisonOperator.GREATER_THAN
    assert params.threshold_amount == 500.0
    assert params.requires_vp_approval is True
    assert params.target_department == "engineering"


def test_classify_per_attendee_rule(classifier):
    rule = "Meals and dining exceeding $60 per attendee require an itemized attendees list."
    params = classifier.classify_rule(rule)

    assert params.scope == TargetScope.PER_ATTENDEE
    assert params.category == SpendCategory.MEALS_ENTERTAINMENT
    assert params.threshold_amount == 60.0
    assert params.requires_itemized_attendees is True


def test_classify_procurement_w9(classifier):
    rule = "Contractor and consultant payments above $10,000 require purchase order matching and an active W-9 tax form."
    params = classifier.classify_rule(rule)

    assert params.domain in [RuleDomain.PROCUREMENT_PO, RuleDomain.TAX_COMPLIANCE]
    assert params.category == SpendCategory.CONTRACTOR_SERVICES
    assert params.threshold_amount == 10000.0
    assert params.requires_purchase_order is True
    assert params.requires_w9 is True


def test_classify_range_rule(classifier):
    rule = "Travel and hotel expenses between $150 and $400 require manager approval."
    params = classifier.classify_rule(rule)

    assert params.category == SpendCategory.TRAVEL_LODGING
    assert params.operator == ComparisonOperator.BETWEEN
    assert params.threshold_amount == 150.0
    assert params.upper_threshold_amount == 400.0
    assert params.requires_manager_approval is True


def test_classify_quickbooks_rule(classifier):
    rule = "QuickBooks rule: Categorize all Uber and Lyft rides under $100 to Account 6200 and Class Sales."
    params = classifier.classify_rule(rule)

    assert params.domain == RuleDomain.QUICKBOOKS_ROUTING
    assert params.category == SpendCategory.TRAVEL_LODGING
    assert params.operator == ComparisonOperator.LESS_THAN
    assert params.threshold_amount == 100.0
    assert params.qb_account == "6200_travel_lodging"
    assert params.qb_class == "Sales"

