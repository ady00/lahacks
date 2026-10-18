import pytest

from engine.schema import FACTS

DINNER = {"text": "Ship the demo unit to the client, $140", "employee_id": "e_newhire"}


@pytest.fixture(autouse=True)
def shipping(monkeypatch):
    from api import cases
    monkeypatch.setattr(cases, "extract", lambda t: {"expense_kind": {"value": "shipping", "p": 0.95}, "client_present": {"p": 0.05}})


def _check(client):
    return client.post("/check", json=DINNER).json()


def test_graph_mirrors_the_case(client):
    c = _check(client)
    g = client.get(f"/cases/{c['case_id']}/graph").json()
    assert g["case_id"] == c["case_id"] and g["verdict"] == "violation" and g["preview"] is False
    assert g["facts_hash"] == g["base_facts_hash"]
    facts = {n["name"]: n for n in g["nodes"] if n["kind"] == "fact"}
    assert set(facts) == set(FACTS)                       # every schema fact is a node, known or not
    assert facts["amount"]["known"] and facts["amount"]["value"] == 140
    assert facts["receipt_attached"]["known"] is False and facts["receipt_attached"]["value"] is None
    assert facts["client_present"]["probability_kind"] == "p_true"
    assert facts["expense_kind"]["probability_kind"] == "value_confidence"
    rules = {n["rule_id"]: n for n in g["nodes"] if n["kind"] == "rule"}
    assert rules["SHIP-100"]["status"] == "violated" and set(rules["SHIP-100"]["evidence_facts"]) == {"amount", "expense_kind", "pre_approved"}
    assert rules["MEAL-when"]["status"] == "inactive"      # meal rule: the kind is shipping
    assert rules["SHIP-100"]["condition"] == "Expense kind is shipping and Amount > 100" and rules["SHIP-100"]["requirement"] == "Pre-approved"
    assert rules["LODGE-300"]["condition"] == "Expense kind is lodging and Amount per Nights > 300"
    edge = next(e for e in g["edges"] if e["id"] == "amount->SHIP-100")
    assert edge["relation"] == "condition" and edge["contradiction_evidence"] is True
    assert any(e["target"] == "verdict" and e["source"] == "SHIP-100" for e in g["edges"])
    assert not any(e["source"] == "MEAL-when" for e in g["edges"] if e["target"] == "verdict")
    assert "coded_account" not in {f["name"] for f in g["editable_fields"]}
    assert g["fix"] == c["fix"]


def test_preview_reproves_without_saving(client):
    c = _check(client)
    g = client.get(f"/cases/{c['case_id']}/graph").json()
    r = client.post(f"/cases/{c['case_id']}/graph/preview",
                    json={"overrides": {"pre_approved": True}, "base_facts_hash": g["base_facts_hash"]})
    assert r.status_code == 200
    p = r.json()
    assert p["preview"] is True and p["saved_verdict"] == "violation" and p["verdict"] == "compliant"
    pre = next(n for n in p["nodes"] if n["id"] == "pre_approved")
    assert pre["value"] is True and pre["changed"] is True and pre["source"] == "preview"
    assert p["facts_hash"] != p["base_facts_hash"]
    assert client.get(f"/cases/{c['case_id']}").json()["verdict"] == "violation"  # nothing saved

    # with approval assumed, clearing the kind leaves the IRS coding rules open: undetermined, and it asks
    r = client.post(f"/cases/{c['case_id']}/graph/preview",
                    json={"overrides": {"expense_kind": None, "pre_approved": True}, "base_facts_hash": g["base_facts_hash"]})
    assert r.json()["verdict"] == "undetermined"
    assert any(q["fact"] == "expense_kind" for q in r.json()["questions"])


def test_preview_rejects_stale_hash_and_bad_values(client):
    c = _check(client)
    assert client.post(f"/cases/{c['case_id']}/graph/preview",
                       json={"overrides": {}, "base_facts_hash": "0" * 64}).status_code == 409
    g = client.get(f"/cases/{c['case_id']}/graph").json()
    for bad in ({"amount": -1}, {"role": "ceo"}, {"coded_account": "travel"}, {"nope": 1}):
        r = client.post(f"/cases/{c['case_id']}/graph/preview", json={"overrides": bad, "base_facts_hash": g["base_facts_hash"]})
        assert r.status_code == 422, bad
    assert client.get("/cases/c_missing/graph").status_code == 404
