"""
Tests for persistent PolicyStore, QueryParser, and Z3 Preflight evaluation.
"""

import pytest
from pathlib import Path
from jev_z3 import (
    PolicyStore,
    QueryParser,
    Z3PreflightEngine,
    PreflightVerdict,
    SpendCategory,
)


@pytest.fixture
def temp_store(tmp_path):
    store_file = tmp_path / "test_policy_store.json"
    return PolicyStore(store_path=store_file)


def test_add_rule_and_list(temp_store):
    initial_count = len(temp_store.list_rules())
    rule_text = "All flights over $500 require VP approval."
    param, conflict = temp_store.add_rule(rule_text, rule_id="RULE-FLIGHT-01")

    assert conflict is None
    assert param.rule_id == "RULE-FLIGHT-01"
    assert param.threshold_amount == 500.0
    assert param.requires_vp_approval is True
    assert len(temp_store.list_rules()) == initial_count + 1


def test_add_conflicting_rule_rejected(temp_store):
    p1, c1 = temp_store.add_rule("All hardware over $1000 is strictly prohibited and rejected.", rule_id="RULE-BLOCK")
    assert c1 is None

    p2, conflict = temp_store.add_rule("All hardware over $1000 requires manager approval.", rule_id="RULE-ALLOW")
    assert conflict is not None
    assert conflict.is_valid is False
    assert "Contradiction detected" in conflict.explanation


def test_query_parser():
    parser = QueryParser()
    intent = parser.parse_query("Can I buy a $650 Datadog monitoring plan for Engineering?")

    assert intent.amount == 650.0
    assert intent.category == SpendCategory.SOFTWARE_SAAS
    assert intent.vendor == "Datadog"
    assert intent.department.lower() == "engineering"


def test_preflight_auto_approved(temp_store):
    parser = QueryParser()
    preflight = Z3PreflightEngine()

    intent = parser.parse_query("Can I buy $30 of pens from Amazon for Admin?")
    rules = temp_store.list_rules()

    result = preflight.evaluate_query(intent, rules)
    assert result.verdict == PreflightVerdict.AUTO_APPROVED
    assert len(result.required_actions) == 0


def test_preflight_conditionally_approved(temp_store):
    parser = QueryParser()
    preflight = Z3PreflightEngine()

    intent = parser.parse_query("Can I buy a $650 Datadog monitoring subscription for Engineering?")
    rules = temp_store.list_rules()

    result = preflight.evaluate_query(intent, rules)
    assert result.verdict == PreflightVerdict.CONDITIONALLY_APPROVED
    assert any("VP" in act for act in result.required_actions)
