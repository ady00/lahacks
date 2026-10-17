import re
from pathlib import Path

import engine
from api import models
from engine.rules import load_policy
from engine.schema import FACTS


def test_policy_real(client):
    d = Path(engine.__file__).parent
    want = load_policy(d / "demo_policy.json", d / "irs_pack.json").version
    r = client.get("/policy")
    j = r.json()
    assert r.headers.get("x-stub") is None
    assert len(j["rules"]) == 24 and re.fullmatch(r"[0-9a-f]{12}", j["version"]) and j["version"] == want
    assert list(j["facts"]) == list(FACTS) and len(j["facts"]) == 10
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
