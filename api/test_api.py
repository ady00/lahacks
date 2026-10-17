import pytest
from api import samples, models

ROUTES = [
    ("post", "/check", {"text": "Client dinner $48", "employee_id": "e_newhire",
                        "timestamp": "2026-10-17T19:30:00-07:00"}),
    ("get", "/cases?awaiting_approval=true", None),
    ("get", "/ledger", None),
    ("post", "/ledger/audit", {"company": "demo"}),
    ("post", "/data/reload", None),
    ("get", "/policy", None),
    ("post", "/policy/audit", None),
    ("post", "/bank-rules/check", {"rules": []}),
    ("get", "/eval", None),
    ("get", "/health", None),
]


@pytest.mark.parametrize("method,path,body", ROUTES)
def test_every_route_answers_as_stub(client, method, path, body):
    r = client.request(method.upper(), path, json=body)
    assert r.status_code == 200


def test_check_stub_is_the_spec_case(client):
    c = client.post("/check", json=ROUTES[0][2]).json()
    assert c["verdict"] == "violation"
    assert c["violations"][0]["rule"] == "3.4"
    assert c["fix"][0] == {"fact": "pre_approved", "from": False, "to": True}
    assert c["awaiting_approval"] is True


def test_check_rejects_nonpositive_amount(client):
    r = client.post("/check", json={"text": "x", "employee_id": "e_newhire", "amount": 0,
                                  "timestamp": "2026-10-17T19:30:00-07:00"})
    assert r.status_code == 422


def test_samples_match_models():
    models.Case.model_validate(samples.SAMPLE_CASE)
    models.Authorization.model_validate(samples.SAMPLE_AUTH)
    models.LedgerRow.model_validate(samples.SAMPLE_LEDGER_ROW)
    models.AuditSummary.model_validate(samples.SAMPLE_AUDIT)
    models.PolicyOut.model_validate(samples.SAMPLE_POLICY)
    models.PolicyAudit.model_validate(samples.SAMPLE_POLICY_AUDIT)
    models.BankRulesOut.model_validate(samples.SAMPLE_BANK_CHECK)
    models.EvalOut.model_validate(samples.SAMPLE_EVAL)


TS = "2026-10-17T19:30:00-07:00"


def test_reviewer_check_unicode_naive_timestamp_repeated(client):
    body = {"text": "Café dîner 東京 — about $48 ☕", "employee_id": "e_newhire", "timestamp": "2026-10-17T19:30:00"}
    a, b = client.post("/check", json=body), client.post("/check", json=body)
    assert a.status_code == b.status_code == 200
    # each real /check mints a new case_id, so compare the proof, not the whole JSON
    proof = lambda r: {k: r.json()[k] for k in ("verdict", "violations", "facts")}
    assert proof(a) == proof(b)
    assert a.json()["facts"]["amount"]["value"] == 48


def test_reviewer_check_amount_edges(client):
    base = {"text": "x", "employee_id": "e_newhire", "timestamp": TS}
    assert client.post("/check", json={**base, "amount": 0.01}).status_code == 200
    assert client.post("/check", json={**base, "amount": -1}).status_code == 422
    assert client.post("/check", json={"text": "x", "timestamp": TS}).status_code == 422
    assert client.post("/bank-rules/check", json={"rules": [{"id": "r1", "contains": ["UBER"]}]}).status_code == 422


def test_reviewer_fixstep_alias_and_fact_types():
    import json
    import pydantic
    by_name = models.FixStep(fact="amount", from_=None, to=35)
    by_alias = models.FixStep.model_validate({"fact": "amount", "from": None, "to": 35})
    assert json.loads(by_name.model_dump_json(by_alias=True)) == {"fact": "amount", "from": None, "to": 35}
    assert by_name == by_alias
    f = json.loads(models.Fact(value=1, source="derived").model_dump_json())
    assert f["value"] == 1 and type(f["value"]) is int
    assert models.Fact(value=True, source="jev", p=0.9).value is True
    with pytest.raises(pydantic.ValidationError):
        models.Fact(value=1, source="model")
