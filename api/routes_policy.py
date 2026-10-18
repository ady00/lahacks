from contextlib import closing

from fastapi import APIRouter, HTTPException

from api import cases, db, models, policy_nl
from engine.rules import Policy

router = APIRouter()


@router.get("/policy", response_model=models.PolicyOut)
def policy():
    from engine.schema import FACTS
    P = cases.POLICY
    return {"version": P.version, "rules": [r.raw for r in P.rules],
            "facts": {n: s._asdict() for n, s in FACTS.items()}}


@router.post("/policy/audit", response_model=models.PolicyAudit)
def policy_audit():
    return cases.POLICY.audit()


@router.get("/policy/irs", response_model=models.IrsReport)
def policy_irs():
    """Every IRS rule with its citation, a Z3-built purchase that breaks it and one that satisfies it (both re-proved),
    and the company rules that already imply it. Reported from the full packs even while the layer is switched off."""
    P = cases.POLICY
    if not cases.IRS_ENABLED:
        with closing(db.connect()) as conn:
            P = Policy(cases.PACK_RULES + db.custom_rules(conn))
    tests = {t["id"]: t for t in P.selftest("irs")}
    rules = [{**r.raw, **tests[r.id]} for r in P.rules if r.layer == "irs"]
    audit = P.audit()
    implied = sum(1 for r in rules if r["implied_by"])
    return {"enabled": cases.IRS_ENABLED, "policy_version": cases.POLICY.version, "rules": rules,
            "audit": {"dead": [d for d in audit["dead"] if d in tests],
                      "conflicts": [c for c in audit["conflicts"] if c["a"] in tests or c["b"] in tests]},
            "summary": {"rules": len(rules), "implied_by_company": implied, "irs_only": len(rules) - implied,
                        "prohibitions": sum(r["prohibition"] for r in rules)}}


@router.post("/policy/layers", response_model=models.PolicyOut)
def policy_layers(body: models.LayersIn):
    """Switch the IRS layer on or off; the live policy is swapped and cases from now on prove against it."""
    with closing(db.connect()) as conn:
        P = cases.reload_policy(db.custom_rules(conn), irs=body.irs)
        db.record_policy(conn, P.version, [r.raw for r in P.rules])
    return policy()


def _next_id(rules: list[dict]) -> str:
    n = 1 + max((int(r["id"][2:]) for r in rules if r["id"].startswith("C-") and r["id"][2:].isdigit()), default=0)
    return f"C-{n}"


def _draft(body: models.RuleIn, existing: list[dict]) -> dict:
    """Compile the rule against the live policy (422 if the DSL is wrong) and audit only the pairs it is in."""
    rule = {"id": _next_id(existing), "layer": "company", "text": body.text.strip(), "when": body.when, "require": body.require, "custom": True}
    try:
        P = Policy(existing + [rule])
    except (KeyError, ValueError, TypeError, AttributeError) as e:
        raise HTTPException(422, f"The rule does not compile: {e!r}")
    audit = P.audit()
    return {"rule": rule, "dead": rule["id"] in audit["dead"],
            "conflicts": [c for c in audit["conflicts"] if rule["id"] in (c["a"], c["b"])]}


@router.post("/policy/rules/draft", response_model=models.RuleDraft)
def rule_draft(body: models.RuleText):
    """Natural language -> a rule, checked by Z3 but not saved."""
    try:
        t = policy_nl.translate(body.text)
    except policy_nl.TranslateError as e:
        raise HTTPException(503, str(e))
    return _draft(models.RuleIn(**t), [r.raw for r in cases.POLICY.rules])


@router.post("/policy/rules", response_model=models.PolicyOut)
def rule_add(body: models.RuleIn):
    """Save a rule (as drafted, or hand-written) and swap the live policy; cases from now on prove against it."""
    with closing(db.connect()) as conn:
        custom = db.custom_rules(conn)
        d = _draft(body, cases.pack_rules() + custom)
        db.put_rule(conn, d["rule"])
        P = cases.reload_policy(custom + [d["rule"]])
        db.record_policy(conn, P.version, [r.raw for r in P.rules])
    return policy()


@router.delete("/policy/rules/{rule_id}", response_model=models.PolicyOut)
def rule_delete(rule_id: str):
    with closing(db.connect()) as conn:
        if not db.delete_rule(conn, rule_id):
            raise HTTPException(404, "only rules added through the dashboard can be removed")
        P = cases.reload_policy(db.custom_rules(conn))
        db.record_policy(conn, P.version, [r.raw for r in P.rules])
    return policy()
