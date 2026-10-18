import json
import pytest
from engine.rules import Policy, load_policy

P = load_policy("engine/demo_policy.json", "engine/irs_pack.json")
P_RAW = json.load(open("engine/demo_policy.json")) + json.load(open("engine/irs_pack.json"))
BASE = dict(role="employee", expense_kind="meal", client_present=False, at_company_event=False, amount=20, hour=12,
            days_since_purchase=0, receipt_attached=True, pre_approved=True, coded_account="meals_50", tenure_days=400)
ENT = dict(BASE, expense_kind="entertainment", coded_account="entertainment_0")

CASES = [
  ("3.4", dict(BASE, amount=36, pre_approved=False), dict(BASE, amount=35, pre_approved=False)),
  ("3.5", dict(BASE, amount=501, receipt_attached=False), dict(BASE, amount=500, receipt_attached=False)),
  ("4.1", dict(BASE, amount=26, days_since_purchase=15, receipt_attached=False), dict(BASE, amount=26, days_since_purchase=14, receipt_attached=False)),
  ("5.1", dict(BASE, role="contractor"), dict(BASE, role="contractor", expense_kind="other", coded_account="other")),
  ("5.2", dict(BASE, role="intern", expense_kind="rideshare", coded_account="travel"), dict(BASE, role="intern", expense_kind="rideshare", coded_account="travel", at_company_event=True)),
  ("5.3", dict(BASE, role="intern"), dict(BASE, role="intern", at_company_event=True, coded_account="meals_100")),
  ("6.1", dict(BASE, hour=22, pre_approved=False), dict(BASE, hour=21, pre_approved=False)),
  ("6.2", dict(BASE, hour=5, pre_approved=False), dict(BASE, hour=6, pre_approved=False)),
  ("6.3", dict(ENT, pre_approved=False), dict(ENT)),
  ("6.4", dict(ENT, amount=101), dict(ENT, amount=100)),
  ("6.5", dict(BASE, client_present=True, amount=151, pre_approved=False), dict(BASE, client_present=True, amount=150, pre_approved=False)),
  ("7.1", dict(BASE, expense_kind="airfare", coded_account="travel", pre_approved=False), dict(BASE, expense_kind="airfare", coded_account="travel")),
  ("7.2", dict(BASE, expense_kind="hotel", coded_account="travel", amount=301, pre_approved=False), dict(BASE, expense_kind="hotel", coded_account="travel", amount=300, pre_approved=False)),
  ("8.1", dict(BASE, expense_kind="software", coded_account="office", pre_approved=False), dict(BASE, expense_kind="software", coded_account="office")),
  ("8.2", dict(BASE, expense_kind="equipment", coded_account="office", amount=251, receipt_attached=False), dict(BASE, expense_kind="equipment", coded_account="office", amount=250, receipt_attached=False)),
  ("9.1", dict(BASE, expense_kind="rideshare", coded_account="travel", amount=76, pre_approved=False), dict(BASE, expense_kind="rideshare", coded_account="travel", amount=75, pre_approved=False)),
  ("10.1", dict(BASE, expense_kind="equipment", coded_account="office", tenure_days=89, pre_approved=False), dict(BASE, expense_kind="equipment", coded_account="office", tenure_days=90, pre_approved=False)),
  ("10.2", dict(BASE, expense_kind="hotel", coded_account="travel", tenure_days=10, pre_approved=False), dict(BASE, expense_kind="hotel", coded_account="travel", tenure_days=10)),
  ("10.3", dict(ENT, tenure_days=0), dict(ENT, tenure_days=90)),
  ("IRS-meal", dict(BASE, coded_account="meals_100"), dict(BASE)),
  ("IRS-meal-event", dict(BASE, at_company_event=True), dict(BASE, at_company_event=True, coded_account="meals_100")),
  ("IRS-ent", dict(ENT, coded_account="other"), dict(ENT)),
  ("IRS-travel", dict(BASE, expense_kind="hotel", coded_account="other"), dict(BASE, expense_kind="hotel", coded_account="travel")),
  ("IRS-office", dict(BASE, expense_kind="software", coded_account="other"), dict(BASE, expense_kind="software", coded_account="office")),
  ("IRS-other", dict(BASE, expense_kind="other", coded_account="travel"), dict(BASE, expense_kind="other", coded_account="other")),
  ("IRS-receipt-60", dict(BASE, days_since_purchase=75, receipt_attached=False, amount=20), dict(BASE, days_since_purchase=75, receipt_attached=True, amount=20)),
  ("IRS-receipt-75", dict(BASE, amount=75, days_since_purchase=1, receipt_attached=False), dict(BASE, amount=74.99, days_since_purchase=1, receipt_attached=False)),
]


def test_base_is_compliant():
    assert P.check(BASE).status == "compliant"


@pytest.mark.parametrize("rule_id,breaking,passing", CASES)
def test_each_rule_bites_and_releases(rule_id, breaking, passing):
    assert rule_id in {v.rule for v in P.check(breaking).violations}
    assert rule_id not in {v.rule for v in P.check(passing).violations}


def test_every_rule_has_a_case():
    assert {c[0] for c in CASES} == set(P.by_id) and len(P.rules) == 27


def test_demo_policy_has_no_dead_rules_or_conflicts():
    assert P.audit() == {"dead": [], "conflicts": []}


def test_audit_finds_an_injected_dead_rule_and_conflict():
    q = Policy(P_RAW + [
      {"id": "D", "layer": "company", "text": "t", "when": {"and": [{"eq": ["role", "intern"]}, {"eq": ["role", "employee"]}]}, "require": "pre_approved"},
      {"id": "X", "layer": "company", "text": "t", "when": {"eq": ["role", "intern"]}, "require": {"eq": ["expense_kind", "meal"]}},
      {"id": "Y", "layer": "company", "text": "t", "when": {"eq": ["role", "intern"]}, "require": {"neq": ["expense_kind", "meal"]}}])
    a = q.audit()
    assert a["dead"] == ["D"] and {(c["a"], c["b"]) for c in a["conflicts"]} == {("X", "Y")} and a["conflicts"][0]["example"]["role"] == "intern"
    json.dumps(a)  # plain Python all the way down


def test_over_35_disagreement_is_exactly_35():
    ge = {**P.by_id["3.4"].raw, "when": {"ge": ["amount", 35]}}
    ex = P.disagreement(P.by_id["3.4"].raw, ge)
    assert ex["amount"] == 35.0 and ex["pre_approved"] is False
    assert P.disagreement(P.by_id["3.4"].raw, P.by_id["3.4"].raw) is None


def test_reviewer_threshold_edges_the_per_rule_cases_miss():
    # 4.1's $25 bound and IRS-receipt-60's 60-day bound: flipping gt->ge survives CASES
    late = dict(BASE, days_since_purchase=15, receipt_attached=False)
    assert "4.1" in {v.rule for v in P.check(dict(late, amount=25.01)).violations}
    assert "4.1" not in {v.rule for v in P.check(dict(late, amount=25)).violations}
    assert "IRS-receipt-60" in {v.rule for v in P.check(dict(BASE, days_since_purchase=61, receipt_attached=False)).violations}
    assert "IRS-receipt-60" not in {v.rule for v in P.check(dict(BASE, days_since_purchase=60, receipt_attached=False)).violations}


def test_reviewer_facts_from_model_audit_repeat_and_empty_policy():
    import z3
    from engine.rules import ENGINE_LOCK
    from engine.schema import FACTS
    with ENGINE_LOCK:
        s = z3.Solver(); s.add(*P.dom, P.vars["amount"] == 12.5)
        assert s.check() == z3.sat
        f = P.facts_from_model(s.model())
    assert set(f) == set(FACTS) and f["amount"] == 12.5 and f["role"] in FACTS["role"].values
    assert P.audit() == P.audit() == {"dead": [], "conflicts": []}
    assert Policy([]).audit() == {"dead": [], "conflicts": []}


def test_reviewer_disagreement_prohibition_vs_approval():
    # 6.4 forbids; a looser "needs approval" version differs exactly on approved entertainment over $100
    loose = {**P.by_id["6.4"].raw, "require": "pre_approved"}
    ex = P.disagreement(P.by_id["6.4"].raw, loose)
    assert ex["expense_kind"] == "entertainment" and ex["amount"] > 100 and ex["pre_approved"] is True
