"""GitLab travel-class, fuel, tip, gift, bill and leave rules: each breaks on one side of its line and holds on the other."""
import pytest

from engine.test_policy_packs import BASE, P

# facts these rules read, set to the values a plain purchase has
DETAILS = dict(travel_class="economy", segment_hours=2, international=False, customer_trip=False, frequent_traveler=False,
               tall_traveler=False, car_above_intermediate=False, rental_car=False, mileage_and_fuel=False, tip_over_20=False,
               cash_equivalent=False, gift_occasion="life_event", includes_fees=False, whole_family_plan=False,
               ap_approved=True, on_leave=False, personal_travel=False)
B = dict(BASE, **DETAILS)
AIR = dict(B, expense_kind="airfare", coded_account="travel")
TRAIN = dict(AIR, expense_kind="train")
CAR = dict(AIR, expense_kind="car_rental")
FUEL = dict(AIR, expense_kind="fuel")
MILE = dict(AIR, expense_kind="mileage", miles=100, amount=50)
GIFT = dict(B, expense_kind="gift", coded_account="other", deductible="limited", amount=20)
NET = dict(B, expense_kind="internet", coded_account="office", traveling=False, amount=60)
PHONE = dict(NET, expense_kind="phone")
COWORK = dict(NET, expense_kind="coworking", days=1, amount=40)
LONG_HAUL = dict(international=True, frequent_traveler=True, customer_trip=True, segment_hours=9)

CASES = [
  ("TRAVEL-lead-21", dict(AIR, international=True, days_before_travel=20, pre_approved=False), dict(AIR, international=True, days_before_travel=21, pre_approved=False)),
  ("AIR-premium", dict(AIR, travel_class="premium", segment_hours=5), dict(AIR, travel_class="premium", segment_hours=5.5)),
  ("AIR-premium", dict(AIR, travel_class="premium", tall_traveler=True, pre_approved=False), dict(AIR, travel_class="premium", tall_traveler=True)),
  ("AIR-business", dict(AIR, travel_class="business", **{**LONG_HAUL, "segment_hours": 8}), dict(AIR, travel_class="business", **LONG_HAUL)),
  ("AIR-business", dict(AIR, travel_class="business", **{**LONG_HAUL, "customer_trip": False}), dict(AIR, travel_class="business", **LONG_HAUL)),
  ("AIR-first", dict(AIR, travel_class="first", **LONG_HAUL), dict(AIR, travel_class="business", **LONG_HAUL)),
  ("TRAIN-class", dict(TRAIN, travel_class="premium", frequent_traveler=True, segment_hours=5), dict(TRAIN, travel_class="premium", frequent_traveler=True, segment_hours=6)),
  ("TRAIN-class", dict(TRAIN, travel_class="business", frequent_traveler=True, segment_hours=6), dict(TRAIN)),
  ("CAR-class", dict(CAR, car_above_intermediate=True), dict(CAR)),
  ("FUEL-300", dict(FUEL, amount=601, days=2, receipt_attached=True), dict(FUEL, amount=600, days=2)),
  ("FUEL-mileage", dict(FUEL, mileage_and_fuel=True), dict(FUEL)),
  ("MILE-rental", dict(MILE, rental_car=True), dict(MILE)),
  ("MEAL-tip", dict(B, tip_over_20=True), dict(B)),
  ("GIFT-cash", dict(GIFT, cash_equivalent=True), dict(GIFT)),
  ("GIFT-baby", dict(GIFT, gift_occasion="baby"), dict(GIFT)),
  ("GIFT-holiday", dict(GIFT, gift_occasion="holiday"), dict(GIFT)),
  ("GIFT-host", dict(GIFT, gift_occasion="host", amount=51), dict(GIFT, gift_occasion="host", amount=50)),
  ("BIZCARD-150", dict(B, expense_kind="business_cards", coded_account="office", amount=151, pre_approved=False), dict(B, expense_kind="business_cards", coded_account="office", amount=150, pre_approved=False)),
  ("DRY-5", dict(AIR, expense_kind="dry_cleaning", nights=5), dict(AIR, expense_kind="dry_cleaning", nights=6)),
  ("NET-fees", dict(NET, includes_fees=True), dict(NET)),
  ("NET-fees", dict(PHONE, includes_fees=True), dict(PHONE)),
  ("PHONE-family", dict(PHONE, whole_family_plan=True), dict(PHONE)),
  ("VISA-ap", dict(AIR, expense_kind="visa", ap_approved=False), dict(AIR, expense_kind="visa")),
  ("LEAVE-no", dict(COWORK, on_leave=True), dict(COWORK)),
  ("LEAVE-no", dict(NET, on_leave=True), dict(NET)),
  ("COWORK-personal", dict(COWORK, personal_travel=True), dict(COWORK)),
]


@pytest.mark.parametrize("rule_id,breaking,passing", CASES)
def test_each_detail_rule_bites_and_releases(rule_id, breaking, passing):
    assert rule_id in {v.rule for v in P.check(breaking).violations}
    assert rule_id not in {v.rule for v in P.check(passing).violations}


def test_every_detail_rule_in_the_pack_has_a_case():
    import json
    new = {r["id"] for r in json.load(open("engine/demo_policy.json"))[30:]}
    assert {c[0] for c in CASES} == new and len(new) == 21


def test_fixes_are_choices_you_control():
    fix = lambda f: [(s.fact, s.to) for s in P.fix(f)]
    assert fix(dict(AIR, travel_class="first")) == [("travel_class", "economy")]
    assert fix(dict(B, tip_over_20=True)) == [("tip_over_20", False)]
    assert fix(dict(AIR, expense_kind="visa", ap_approved=False)) == [("ap_approved", True)]
    assert P.fix(dict(GIFT, gift_occasion="baby")) is None and P.fix(dict(MILE, rental_car=True)) is None


def test_premium_seat_with_unknown_segment_asks_for_it():
    f = {k: v for k, v in dict(AIR, travel_class="premium").items() if k != "segment_hours"}
    d = P.decide(f, {})
    assert d.verdict.status == "undetermined" and "segment_hours" in d.questions
