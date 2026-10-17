def test_bank_rules_check_finds_shadowed_rule(client):
    r = client.post("/bank-rules/check", json={"rules": [
        {"id": "r1", "contains": ["UBER"], "category": "Travel"},
        {"id": "r2", "contains": ["UBER", "EATS"], "category": "Meals"}]})
    assert r.status_code == 200 and "x-stub" not in r.headers
    assert r.json()["shadowed"] == [{"rule": "r2", "by": ["r1"]}]


def test_bank_rules_check_empty(client):
    r = client.post("/bank-rules/check", json={"rules": []})
    assert r.json() == {"shadowed": [], "overlaps": []} and "x-stub" not in r.headers
