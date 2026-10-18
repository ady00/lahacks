import re
from pathlib import Path

import engine
from api import models
from engine.rules import load_policy
from engine.schema import FACTS


def test_policy_real(client):
    d = Path(engine.__file__).parent
    packs = load_policy(d / "demo_policy.json", d / "irs_pack.json")
    r = client.get("/policy")
    j = r.json()
    assert r.headers.get("x-stub") is None
    assert len(j["rules"]) == len(packs.rules) and re.fullmatch(r"[0-9a-f]{12}", j["version"]) and j["version"] == packs.version
    assert list(j["facts"]) == list(FACTS)
    assert all({"id", "layer", "text", "when", "require"} <= set(x) for x in j["rules"])
    assert all(isinstance(f["values"], (list, type(None))) for f in j["facts"].values())
    models.PolicyOut.model_validate(j)


def test_policy_audit_real(client):
    r = client.post("/policy/audit")
    assert r.headers.get("x-stub") is None and r.json() == {"dead": [], "conflicts": []}


def test_reviewer_policy_version_matches_health_and_rules_match_pack(client):
    import json
    d = Path(engine.__file__).parent
    raw = json.loads((d / "demo_policy.json").read_text()) + json.loads((d / "irs_pack.json").read_text())
    j = client.get("/policy").json()
    assert j["version"] == client.get("/health").json()["policy_version"]
    assert json.dumps(j["rules"]) == json.dumps(raw)
    j["rules"][0]["when"] = "MUTATED"
    j["facts"]["role"]["values"].append("x")
    j2 = client.get("/policy").json()
    assert json.dumps(j2["rules"]) == json.dumps(raw) and j2["facts"]["role"]["values"] == ["employee", "contractor", "intern"]


def test_reviewer_policy_facts_non_enum_have_null_values(client):
    f = client.get("/policy").json()["facts"]
    assert f["amount"]["values"] is None and f["hour"]["lo"] == 0 and f["hour"]["hi"] == 23
    assert all(set(v) == {"kind", "values", "lo", "hi", "mutable", "weight", "derived"} for v in f.values())


def test_reviewer_policy_audit_repeated_fast_and_method(client):
    import time
    t = time.perf_counter()
    outs = [client.post("/policy/audit").json() for _ in range(3)]
    assert time.perf_counter() - t < 3 and all(o == {"dead": [], "conflicts": []} for o in outs)
    assert client.get("/policy/audit").status_code == 405


def test_rules_add_draft_delete(client, monkeypatch):
    from api import policy_nl
    monkeypatch.setattr(policy_nl, "translate", lambda text: {"text": "Hotels over $900 are never reimbursed.",
        "when": {"and": [{"eq": ["expense_kind", "lodging"]}, {"gt": ["amount", 900]}]}, "require": False})
    v0 = client.get("/health").json()["policy_version"]
    n = len(client.get("/policy").json()["rules"])
    d = client.post("/policy/rules/draft", json={"text": "no hotels over 900 bucks"}).json()
    assert d["rule"]["id"] == "C-1" and d["rule"]["custom"] and d["dead"] is False and d["conflicts"] == []
    assert len(client.get("/policy").json()["rules"]) == n  # a draft saves nothing
    r = client.post("/policy/rules", json={k: d["rule"][k] for k in ("text", "when", "require")})
    assert r.status_code == 200 and len(r.json()["rules"]) == n + 1 and r.json()["version"] != v0
    assert client.get("/health").json()["policy_version"] == r.json()["version"]  # the live policy was swapped
    # a hotel for $1,200 is now a violation of C-1
    c = client.post("/check", json={"text": "Hotel for the conference, $1200", "employee_id": "e_newhire"}).json()
    assert any(v["rule"] == "C-1" for v in c["violations"]) or c["verdict"] != "compliant"
    assert client.post("/policy/rules", json={"text": "bad", "when": {"gt": ["no_such_fact", 1]}, "require": True}).status_code == 422
    assert client.delete("/policy/rules/GEN-receipt").status_code == 404
    r = client.delete("/policy/rules/C-1")
    assert r.status_code == 200 and len(r.json()["rules"]) == n and r.json()["version"] == v0


def test_rule_draft_translator_unavailable(client, monkeypatch):
    from api import policy_nl
    monkeypatch.setattr(policy_nl, "_claude", lambda: None)
    r = client.post("/policy/rules/draft", json={"text": "Interns may not fly"})
    assert r.status_code == 503 and "Claude" in r.json()["detail"]


def test_irs_report_proves_every_statutory_rule_both_ways(client):
    r = client.get("/policy/irs")
    j = r.json()
    assert r.status_code == 200 and j["enabled"] is True and j["audit"] == {"dead": [], "conflicts": []}
    irs = [x for x in client.get("/policy").json()["rules"] if x["layer"] == "irs"]
    assert [x["id"] for x in j["rules"]] == [x["id"] for x in irs] and len(irs) >= 13
    for x in j["rules"]:
        assert x["cite"] and x["url"].startswith("https://") and x["text"] and x["when"] is not None
        assert x["breaks"]["verdict"] == "violation" and x["id"] in x["breaks"]["violations"] and x["ms"] >= 0
        assert x["holds"] is None if x["prohibition"] else x["holds"]["verdict"] == "compliant"
    by = {x["id"]: x for x in j["rules"]}
    assert by["IRS-receipt-75"]["implied_by"] == ["GEN-receipt"] and by["IRS-commute"]["prohibition"] is True
    assert j["summary"]["rules"] == len(irs) and j["summary"]["implied_by_company"] >= 1
    assert j["summary"]["rules"] == j["summary"]["implied_by_company"] + j["summary"]["irs_only"]
    models.IrsReport.model_validate(j)


def test_irs_layer_toggle_swaps_the_live_policy(client):
    v0 = client.get("/health").json()["policy_version"]
    r = client.post("/policy/layers", json={"irs": False})
    assert r.status_code == 200 and all(x["layer"] != "irs" for x in r.json()["rules"]) and r.json()["version"] != v0
    assert client.get("/health").json()["policy_version"] == r.json()["version"]
    assert client.get("/policy/irs").json()["enabled"] is False
    c = client.post("/check", json={"text": "Client dinner Thursday with Acme's CFO, about $48.", "employee_id": "e_newhire"}).json()
    assert "coded_account" not in c["facts"] and "deductible" not in c["facts"]  # nothing derives the tax coding now
    r = client.post("/policy/layers", json={"irs": True})
    assert r.json()["version"] == v0 and client.get("/policy/irs").json()["enabled"] is True
    c = client.post("/check", json={"text": "Client dinner Thursday with Acme's CFO, about $48.", "employee_id": "e_newhire"}).json()
    assert c["facts"]["coded_account"]["value"] == "meals_50" and c["facts"]["deductible"]["value"] == "50%"
