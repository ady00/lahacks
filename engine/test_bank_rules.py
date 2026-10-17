from engine.bank_rules import check_bank_rules


def test_uber_eats_after_uber_is_shadowed():
    out = check_bank_rules([{"id": "r1", "contains": ["UBER"], "category": "Travel"}, {"id": "r2", "contains": ["UBER", "EATS"], "category": "Meals"}])
    assert out["shadowed"] == [{"rule": "r2", "by": ["r1"]}]


def test_uber_eats_before_uber_overlaps_with_an_example():
    out = check_bank_rules([{"id": "r1", "contains": ["UBER", "EATS"], "category": "Meals"}, {"id": "r2", "contains": ["UBER"], "category": "Travel"}])
    assert out["shadowed"] == [] and out["overlaps"][0]["a"] == "r1" and "UBER" in out["overlaps"][0]["example"]["description"]


def test_unrelated_words_are_filtered_as_noise():
    out = check_bank_rules([{"id": "r1", "contains": ["UBER"], "category": "Travel"}, {"id": "r2", "contains": ["AMAZON"], "category": "Office"}])
    assert out["overlaps"] == []


def test_disjoint_amount_ranges_do_not_overlap():
    out = check_bank_rules([{"id": "r1", "contains": ["STARBUCKS"], "amount_max": 20, "category": "Meals"}, {"id": "r2", "contains": ["STARBUCKS"], "amount_min": 20.01, "category": "Office"}])
    assert out["overlaps"] == [] and out["shadowed"] == []


def test_contract_example_is_shadowed_and_overlaps():
    out = check_bank_rules([{"id": "r1", "contains": ["UBER"], "category": "Travel"},
                            {"id": "r2", "contains": ["UBER", "EATS"], "amount_min": 0, "amount_max": 60, "category": "Meals"}])
    assert out["shadowed"] == [{"rule": "r2", "by": ["r1"]}]
    ov = out["overlaps"][0]
    assert (ov["a"], ov["b"]) == ("r1", "r2")
    ex = ov["example"]
    assert "UBER" in ex["description"] and "EATS" in ex["description"] and 0 <= ex["amount"] <= 60


def test_empty_contains_matches_everything_and_words_are_uppercased():
    out = check_bank_rules([{"id": "r1", "contains": [], "category": "Other"},
                            {"id": "r2", "contains": ["uber"], "category": "Travel"}])
    assert out["shadowed"] == [{"rule": "r2", "by": ["r1"]}]
    assert out["overlaps"][0]["example"]["description"].find("UBER") >= 0


def test_shadowed_by_union_of_earlier_rules():
    out = check_bank_rules([{"id": "r1", "contains": ["X"], "amount_max": 10, "category": "A"},
                            {"id": "r2", "contains": ["X"], "amount_min": 10, "category": "A"},
                            {"id": "r3", "contains": ["X"], "category": "B"}])
    assert out["shadowed"] == [{"rule": "r3", "by": []}]


def test_empty_list():
    assert check_bank_rules([]) == {"shadowed": [], "overlaps": []}


def test_reviewer_non_nested_ranges_overlap_inside_the_intersection():
    out = check_bank_rules([{"id": "r1", "contains": ["SHELL"], "amount_min": 10, "amount_max": 50, "category": "Auto"},
                            {"id": "r2", "contains": ["SHELL"], "amount_min": 40, "amount_max": 90, "category": "Meals"}])
    assert out["shadowed"] == [] and 40 <= out["overlaps"][0]["example"]["amount"] <= 50


def test_reviewer_point_range_is_shadowed_by_identical_point_range():
    out = check_bank_rules([{"id": "r1", "contains": ["SHELL"], "amount_min": 25, "amount_max": 25, "category": "Auto"},
                            {"id": "r2", "contains": ["shell"], "amount_min": 25, "amount_max": 25, "category": "Meals"}])
    assert out["shadowed"] == [{"rule": "r2", "by": ["r1"]}] and out["overlaps"][0]["example"]["amount"] == 25.0


def test_reviewer_mixed_case_words_and_repeat_call_are_stable():
    rules = [{"id": "r1", "contains": ["uber"], "category": "Travel"}, {"id": "r2", "contains": ["Uber", "eats"], "category": "Meals"}]
    first = check_bank_rules(rules)
    assert first["shadowed"] == [{"rule": "r2", "by": ["r1"]}] and check_bank_rules(rules) == first


MERCHANTS = ["UBER", "LYFT", "AMAZON", "STARBUCKS", "SHELL", "DELTA", "STAPLES", "COSTCO", "HILTON", "ZOOM"]


def test_thirty_rules_over_ten_merchants_is_fast():
    import time
    variants = [([m], "Travel") for m in MERCHANTS] + [([m, "EATS"], "Meals") for m in MERCHANTS] + [([m, "MKT"], "Office") for m in MERCHANTS]
    rules = [{"id": f"r{k}", "contains": ws, "category": cat} for k, (ws, cat) in enumerate(variants)]
    t = time.perf_counter()
    out = check_bank_rules(rules)
    assert time.perf_counter() - t < 2
    assert len(out["shadowed"]) == 20 and len(out["overlaps"]) == 20


def test_contract_example_amount_is_positive_and_in_range():
    out = check_bank_rules([{"id": "r1", "contains": ["UBER"], "category": "Travel"},
                            {"id": "r2", "contains": ["UBER", "EATS"], "amount_min": 0, "amount_max": 60, "category": "Meals"}])
    assert 0 < out["overlaps"][0]["example"]["amount"] <= 60


def test_negative_only_rule_matches_nothing():
    out = check_bank_rules([{"id": "r1", "contains": ["UBER"], "amount_max": -5, "category": "Travel"},
                            {"id": "r2", "contains": ["UBER"], "category": "Meals"}])
    assert out == {"shadowed": [], "overlaps": []}


def test_min_zero_rule_shadows_unbounded_rule_on_positive_amounts():
    out = check_bank_rules([{"id": "r1", "contains": ["UBER"], "amount_min": 0, "category": "Travel"},
                            {"id": "r2", "contains": ["UBER"], "category": "Meals"}])
    assert out["shadowed"] == [{"rule": "r2", "by": ["r1"]}]


def test_threaded_calls_do_not_crash():
    import subprocess, sys
    code = """
import threading
from engine.bank_rules import check_bank_rules
R = [{"id": "r1", "contains": ["UBER"], "category": "Travel"},
     {"id": "r2", "contains": ["UBER", "EATS"], "amount_min": 0, "amount_max": 60, "category": "Meals"}]
def go():
    for _ in range(20):
        assert check_bank_rules(R)["shadowed"] == [{"rule": "r2", "by": ["r1"]}]
ts = [threading.Thread(target=go) for _ in range(8)]
[t.start() for t in ts]; [t.join() for t in ts]
"""
    assert subprocess.run([sys.executable, "-c", code], timeout=120).returncode == 0
