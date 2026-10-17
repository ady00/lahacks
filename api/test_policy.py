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
