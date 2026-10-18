import json
import pytest
from engine.rules import Policy, load_policy

P = load_policy("engine/demo_policy.json", "engine/irs_pack.json")
P_RAW = json.load(open("engine/demo_policy.json")) + json.load(open("engine/irs_pack.json"))
# a $20 solo meal on a business trip, everything attached and approved, booked early through Navan
BASE = dict(role="employee", expense_kind="meal", client_present=False, at_company_event=False, traveling=True,
            government_present=False, round_trip=False, amount=20, hour=12, days_since_purchase=0, days_before_travel=30,
            tenure_days=400, attendees=1, nights=1, days=1, receipt_attached=True, pre_approved=True, approved_issue=True,
            booked_via_navan=True, coded_account="meals_50", deductible="50%", companion_present=False, commuting=False, miles=1,
            travel_class="economy", segment_hours=1, international=False, customer_trip=False, frequent_traveler=False, tall_traveler=False,
            car_above_intermediate=False, rental_car=False, mileage_and_fuel=False, tip_over_20=False, cash_equivalent=False,
            gift_occasion="life_event", includes_fees=False, whole_family_plan=False, ap_approved=True, on_leave=False, personal_travel=False,
            multi_month_bill=False, above_fair_price=False, collision_waiver=False, hotel_extras=False, rail_pass=False, beyond_50km=False,
            non_dedicated_venue=False, deposit_or_advance=False, coworking_full_month=False, equipment_off_list=False, domain_name=False)
AIR = dict(BASE, expense_kind="airfare", coded_account="travel", pre_approved=False)
LODGE = dict(BASE, expense_kind="lodging", coded_account="travel", pre_approved=False)
RIDE = dict(BASE, expense_kind="rideshare", coded_account="travel", pre_approved=False)
NET = dict(BASE, expense_kind="internet", coded_account="office")
BOOK = dict(BASE, expense_kind="books", coded_account="other")
TRAIN = dict(AIR, expense_kind="train")
CAR = dict(AIR, expense_kind="car_rental")
COWORK = dict(NET, expense_kind="coworking", days=3, amount=200)

CASES = [
  ("GEN-receipt", dict(BASE, amount=51, days_since_purchase=1, receipt_attached=False), dict(BASE, amount=50, days_since_purchase=1, receipt_attached=False)),
  ("GEN-5000", dict(BASE, amount=5001), dict(BASE, amount=5000)),
  ("GEN-90d", dict(BASE, days_since_purchase=91, pre_approved=False), dict(BASE, days_since_purchase=90, pre_approved=False)),
  ("TRAVEL-navan", dict(AIR, booked_via_navan=False), dict(AIR)),
  ("TRAVEL-lead-14", dict(AIR, days_before_travel=13), dict(AIR, days_before_travel=14)),
  ("TRAVEL-lead-7", dict(LODGE, days_before_travel=6), dict(LODGE, days_before_travel=7)),
  ("LODGE-300", dict(LODGE, amount=601, nights=2), dict(LODGE, amount=600, nights=2)),
  ("MEAL-when", dict(BASE, traveling=False), dict(BASE, traveling=False, client_present=True)),
  ("MEAL-120", dict(BASE, amount=241, days=2), dict(BASE, amount=240, days=2)),
  ("MEAL-team-80", dict(BASE, at_company_event=True, coded_account="meals_100", deductible="100%", amount=81), dict(BASE, at_company_event=True, coded_account="meals_100", deductible="100%", amount=80)),
  ("MEAL-client-80", dict(BASE, client_present=True, amount=161, attendees=2), dict(BASE, client_present=True, amount=160, attendees=2)),
  ("MEAL-gov", dict(BASE, client_present=True, government_present=True), dict(BASE, client_present=True)),
  ("RIDE-150", dict(RIDE, amount=151), dict(RIDE, amount=150)),
  ("RIDE-150", dict(RIDE, amount=301, round_trip=True), dict(RIDE, amount=300, round_trip=True)),
  ("PARK-150", dict(RIDE, expense_kind="parking", amount=301, days=2), dict(RIDE, expense_kind="parking", amount=300, days=2)),
  ("NET-travel-50", dict(NET, amount=51), dict(NET, amount=50)),
  ("NET-home-100", dict(NET, traveling=False, amount=101), dict(NET, traveling=False, amount=100)),
  ("NET-home-100", dict(NET, traveling=False, amount=40, receipt_attached=False), dict(NET, traveling=False, amount=40)),
  ("PHONE-100", dict(NET, expense_kind="phone", amount=101), dict(NET, expense_kind="phone", amount=100)),
  ("COWORK-day", dict(NET, expense_kind="coworking", days=3, amount=301), dict(NET, expense_kind="coworking", days=3, amount=300)),
  ("COWORK-month", dict(NET, expense_kind="coworking", days=6, amount=701), dict(NET, expense_kind="coworking", days=6, amount=700)),
  ("COWORK-month", dict(NET, expense_kind="coworking", days=6, amount=500, pre_approved=False), dict(NET, expense_kind="coworking", days=6, amount=500)),
  ("EQUIP-1500", dict(NET, expense_kind="equipment", tenure_days=100, amount=1501), dict(NET, expense_kind="equipment", tenure_days=100, amount=1500)),
  ("EQUIP-500", dict(NET, expense_kind="equipment", amount=501), dict(NET, expense_kind="equipment", amount=500)),
  ("LAPTOP-it", dict(NET, expense_kind="laptop", approved_issue=False), dict(NET, expense_kind="laptop")),
  ("DEVICE-no", dict(NET, expense_kind="personal_device"), dict(NET, expense_kind="equipment")),
  ("SUPPLY-50", dict(NET, expense_kind="office_supplies", amount=51), dict(NET, expense_kind="office_supplies", amount=50)),
  ("BOOK-60", dict(BOOK, amount=61), dict(BOOK, amount=60)),
  ("GD-issue", dict(BOOK, expense_kind="development", approved_issue=False), dict(BOOK, expense_kind="development")),
  ("GIFT-125", dict(BOOK, expense_kind="gift", amount=126), dict(BOOK, expense_kind="gift", amount=125)),
  ("SHIP-100", dict(NET, expense_kind="shipping", amount=101, pre_approved=False), dict(NET, expense_kind="shipping", amount=100, pre_approved=False)),
  ("SW-no", dict(NET, expense_kind="software"), dict(NET, expense_kind="equipment")),
  ("SWAG-no", dict(BOOK, expense_kind="swag"), dict(BOOK, expense_kind="other")),
  # GitLab handbook, second pass; the travel-class, fuel, tip, gift, bill and leave rules are in test_gitlab_details.py
  ("PRICE-20", dict(AIR, above_fair_price=True), dict(AIR, above_fair_price=True, pre_approved=True)),
  ("LODGE-navan-ap", dict(LODGE, booked_via_navan=False, pre_approved=True, ap_approved=False), dict(LODGE, booked_via_navan=False, pre_approved=True)),
  ("LODGE-extras", dict(LODGE, hotel_extras=True), dict(LODGE)),
  ("CAR-cdw", dict(CAR, collision_waiver=True), dict(CAR, collision_waiver=True, international=True)),
  ("TRAIN-pass", dict(TRAIN, rail_pass=True), dict(TRAIN)),
  ("COWORK-50km", dict(COWORK, traveling=False, beyond_50km=True), dict(COWORK, traveling=True, beyond_50km=True)),
  ("COWORK-venue", dict(COWORK, non_dedicated_venue=True), dict(COWORK)),
  ("COWORK-deposit", dict(COWORK, deposit_or_advance=True), dict(COWORK)),
  ("NET-cowork", dict(NET, traveling=False, amount=80, coworking_full_month=True), dict(NET, traveling=False, amount=80)),
  ("GEN-monthly", dict(NET, traveling=False, amount=80, multi_month_bill=True), dict(NET, traveling=False, amount=80)),
  ("EQUIP-list", dict(NET, expense_kind="equipment", amount=400, equipment_off_list=True, pre_approved=False), dict(NET, expense_kind="equipment", amount=400, equipment_off_list=True)),
  ("GEN-domain", dict(BOOK, expense_kind="other", domain_name=True), dict(BOOK, expense_kind="other")),
  ("IRS-meal", dict(BASE, coded_account="meals_100"), dict(BASE)),
  ("IRS-meal", dict(BASE, deductible="100%"), dict(BASE)),
  ("IRS-ent", dict(BASE, expense_kind="entertainment", coded_account="other"), dict(BASE, expense_kind="entertainment", coded_account="entertainment_0", deductible="0%")),
  ("IRS-mileage", dict(AIR, expense_kind="mileage", miles=100, amount=72.51), dict(AIR, expense_kind="mileage", miles=100, amount=72.50)),
  ("IRS-lodging-receipt", dict(LODGE, amount=40, days_since_purchase=1, receipt_attached=False), dict(LODGE, amount=40, days_since_purchase=1)),
  ("IRS-companion", dict(AIR, companion_present=True, deductible="100%"), dict(AIR, companion_present=True, deductible="limited")),
  ("IRS-commute", dict(RIDE, commuting=True), dict(RIDE)),
  ("IRS-gift-25", dict(BOOK, expense_kind="gift", amount=51, attendees=2, deductible="100%"), dict(BOOK, expense_kind="gift", amount=50, attendees=2, deductible="100%")),
  ("IRS-meal-event", dict(BASE, at_company_event=True), dict(BASE, at_company_event=True, coded_account="meals_100", deductible="100%")),
  ("IRS-travel", dict(LODGE, coded_account="other"), dict(LODGE)),
  ("IRS-office", dict(NET, expense_kind="equipment", coded_account="other"), dict(NET, expense_kind="equipment")),
  ("IRS-other", dict(BOOK, coded_account="travel"), dict(BOOK)),
  ("IRS-receipt-60", dict(BASE, days_since_purchase=75, receipt_attached=False), dict(BASE, days_since_purchase=75)),
  ("IRS-receipt-75", dict(BASE, amount=75, days_since_purchase=1, receipt_attached=False), dict(BASE, amount=74.99, days_since_purchase=1, receipt_attached=False)),
]


def test_base_is_compliant():
    assert P.check(BASE).status == "compliant"


def hits(v):
    """Company violations and IRS notes together: the rule fired either way."""
    return {x.rule for x in v.violations} | {x.rule for x in v.notes}


@pytest.mark.parametrize("rule_id,breaking,passing", CASES)
def test_each_rule_bites_and_releases(rule_id, breaking, passing):
    assert rule_id in hits(P.check(breaking))
    assert rule_id not in hits(P.check(passing))


def test_every_rule_has_a_case():
    from engine.test_gitlab_details import CASES as DETAIL_CASES  # here, not at import: that module imports BASE from us
    assert {c[0] for c in CASES} | {c[0] for c in DETAIL_CASES} == set(P.by_id) and len(P.rules) == len(P_RAW)


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


def test_over_50_disagreement_is_exactly_50():
    ge = {**P.by_id["GEN-receipt"].raw, "when": {"and": [{"ge": ["amount", 50]}, {"gt": ["days_since_purchase", 0]}]}}
    ex = P.disagreement(P.by_id["GEN-receipt"].raw, ge)
    assert ex["amount"] == 50.0 and ex["receipt_attached"] is False and ex["days_since_purchase"] > 0
    assert P.disagreement(P.by_id["GEN-receipt"].raw, P.by_id["GEN-receipt"].raw) is None


def test_reviewer_threshold_edges_the_per_rule_cases_miss():
    # per-night and per-person bounds are exact, and IRS-receipt-60's 60-day bound
    two = dict(LODGE, nights=2, receipt_attached=True)
    assert "LODGE-300" in {v.rule for v in P.check(dict(two, amount=600.01)).violations}
    assert "LODGE-300" not in {v.rule for v in P.check(dict(two, amount=600)).violations}
    three = dict(BASE, client_present=True, attendees=3)
    assert "MEAL-client-80" in {v.rule for v in P.check(dict(three, amount=240.01)).violations}
    assert "MEAL-client-80" not in {v.rule for v in P.check(dict(three, amount=240)).violations}
    assert "IRS-receipt-60" in hits(P.check(dict(BASE, days_since_purchase=61, receipt_attached=False)))
    assert "IRS-receipt-60" not in hits(P.check(dict(BASE, days_since_purchase=60, receipt_attached=False)))


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
    # SW-no forbids; a looser "needs approval" version differs exactly on approved software
    loose = {**P.by_id["SW-no"].raw, "require": "pre_approved"}
    ex = P.disagreement(P.by_id["SW-no"].raw, loose)
    assert ex["expense_kind"] == "software" and ex["pre_approved"] is True


def test_per_unit_limit_asks_for_the_divisor_then_fixes_the_amount():
    d = P.decide({k: v for k, v in dict(BASE, client_present=True, amount=300).items() if k != "attendees"}, {})
    assert d.verdict.status == "undetermined" and d.questions == ["attendees"]
    d = P.decide(dict(BASE, client_present=True, amount=300, attendees=3), {})
    assert [v.rule for v in d.verdict.violations] == ["MEAL-client-80"]
    assert [(s.fact, s.to) for s in d.fix] == [("amount", 240.0)]


def test_selftest_builds_a_breaking_and_a_holding_purchase_for_every_irs_rule():
    from engine.schema import FACTS
    out = P.selftest("irs")
    assert [r["id"] for r in out] == [r.id for r in P.rules if r.layer == "irs"] and len(out) == 13
    assert [r["id"] for r in out if r["prohibition"]] == ["IRS-commute"]
    for r in out:
        assert r["id"] in r["breaks"]["violations"]  # an IRS rule fires as a note; the verdict stays company policy's
        assert set(r["breaks"]["facts"]) == set(FACTS)
        if r["prohibition"]:  # IRS-commute: when its condition holds the purchase is simply not allowed
            assert r["holds"] is None
        else:
            assert r["holds"]["verdict"] == "compliant" and r["id"] not in r["holds"]["violations"] and set(r["holds"]["facts"]) == set(FACTS)
        assert set(r["facts_used"]) <= set(FACTS) and r["ms"] >= 0
    json.dumps(out)  # plain Python all the way down


def test_selftest_names_the_company_rules_that_already_imply_an_irs_rule():
    by = {r["id"]: r for r in P.selftest("irs")}
    assert by["IRS-receipt-75"]["implied_by"] == ["GEN-receipt"]   # $75+ after day 0 is inside "over $50 needs a receipt"
    assert by["IRS-receipt-60"]["implied_by"] == []                # a $10 expense 61 days old: no company rule asks for a receipt
    assert by["IRS-meal"]["implied_by"] == []
    # the breaker for IRS-receipt-75 cannot avoid GEN-receipt; the one for IRS-meal trips nothing else
    assert by["IRS-receipt-75"]["breaks"]["also"] == ["GEN-receipt"] and by["IRS-meal"]["breaks"]["also"] == []
    assert by["IRS-meal"]["breaks"]["because"]["IRS-meal"]  # the unsat core names the deciding facts


def test_irs_rules_carry_a_citation():
    for r in P.rules:
        if r.layer == "irs":
            assert r.raw["cite"] and r.raw["url"].startswith("https://")
