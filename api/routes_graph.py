"""GET /cases/{id}/graph and POST /cases/{id}/graph/preview: a case as facts -> rules -> verdict.

Shape is the dashboard's `web/lib/graph.ts` (CaseGraph). Fact node ids are fact names, rule node ids are rule ids,
the verdict node is "verdict". Preview re-proves the saved case with overridden facts and saves nothing.
"""
import hashlib
import json
from contextlib import closing
from typing import Any

import z3
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api import cases, db
from engine.rules import ENGINE_LOCK, _names, _sat
from engine.schema import FACTS, validate_value

router = APIRouter()

LABEL = {
    "role": "Role", "expense_kind": "Expense kind", "coded_account": "Coded account", "amount": "Amount",
    "hour": "Hour of purchase", "days_since_purchase": "Days since purchase", "receipt_attached": "Receipt attached",
    "pre_approved": "Pre-approved", "client_present": "Client present", "at_company_event": "At company event",
    "tenure_days": "Days since start date", "days_before_travel": "Days booked ahead", "attendees": "People",
    "nights": "Nights", "days": "Days covered", "approved_issue": "Approved issue", "booked_via_navan": "Booked via Navan",
    "traveling": "On a business trip", "round_trip": "Round trip", "government_present": "Government official present",
    "deductible": "Deductible", "miles": "Miles", "companion_present": "Spouse or family along", "commuting": "Commuting",
    "travel_class": "Seat class", "segment_hours": "Segment hours", "international": "International",
    "customer_trip": "Customer, speaking or conference trip", "frequent_traveler": "Frequent traveler",
    "tall_traveler": "Over 6'5\"", "car_above_intermediate": "Car above intermediate", "rental_car": "Rental car",
    "mileage_and_fuel": "Mileage and fuel both claimed", "tip_over_20": "Tip over 20%", "cash_equivalent": "Cash or gift card",
    "gift_occasion": "Gift occasion", "includes_fees": "Includes setup or hardware fees", "whole_family_plan": "Whole family plan",
    "ap_approved": "AP Admin approved", "on_leave": "On leave", "personal_travel": "Personal travel",
}
_OPS = {"eq": "is", "neq": "is not", "gt": ">", "ge": "≥", "lt": "<", "le": "≤"}


def _text(expr) -> str:
    """Rule JSON -> one readable line."""
    if isinstance(expr, bool):
        return "always" if expr else "never"
    if isinstance(expr, str):
        return LABEL.get(expr, expr)
    (op, arg), = expr.items()
    if op in ("and", "or"):
        parts = [f"({_text(e)})" if isinstance(e, dict) and next(iter(e)) in ("and", "or") else _text(e) for e in arg]
        return f" {op} ".join(parts)
    if op == "not":
        return f"not {_text(arg)}"
    name, lit = arg
    if op == "in":
        return f"{LABEL.get(name, name)} in {', '.join(map(str, lit))}"
    if isinstance(name, dict):  # {"per": [fact, by]}
        name = " per ".join(LABEL.get(n, n) for n in name["per"])
    return f"{LABEL.get(name, name)} {_OPS[op]} {lit}"


def _hash(values: dict) -> str:
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def _state(eqs: list, expr: z3.BoolRef) -> str:
    """Under ENGINE_LOCK: is `expr` forced true, forced false, or open given the known facts."""
    if not _sat(*eqs, z3.Not(expr)):
        return "true"
    if not _sat(*eqs, expr):
        return "false"
    return "unknown"


def _fact_node(name: str, f: dict | None, changed: set[str]) -> dict:
    spec = FACTS[name]
    p = f.get("p") if f else None
    return {"id": name, "kind": "fact", "name": name, "label": LABEL.get(name, name),
            "value": f["value"] if f else None, "known": f is not None, "source": f["source"] if f else "",
            "p": p, "probability_kind": None if p is None else ("p_true" if spec.kind == "bool" else "value_confidence"),
            "evidence_ref": None, "changed": name in changed}


def graph(case: dict, preview: bool, saved_verdict: str, changed: set[str], base_hash: str) -> dict:
    facts = case["facts"]
    values = {n: f["value"] for n, f in facts.items()}
    because = {v["rule"]: set(v["because"]) for v in case["violations"]}
    nodes = [_fact_node(n, facts.get(n), changed) for n in FACTS]
    edges = []
    with ENGINE_LOCK:
        eqs = list(cases.POLICY.facts_eq(values).values())
        for r in cases.POLICY.rules:
            cond, req = _state(eqs, r.when), _state(eqs, r.require)
            cf, rf = sorted(_names(r.raw["when"])), sorted(_names(r.raw["require"]))
            status = ("violated" if r.id in because else "inactive" if cond == "false"
                      else "satisfied" if cond == "true" and req == "true" else "uncertain")
            nodes.append({"id": r.id, "kind": "rule", "rule_id": r.id, "label": r.text, "layer": r.layer,
                          "status": status, "condition": _text(r.raw["when"]), "requirement": _text(r.raw["require"]),
                          "condition_state": cond, "requirement_state": req,
                          "condition_facts": cf, "requirement_facts": rf, "evidence_facts": sorted(because.get(r.id, ()))})
            for name in sorted(set(cf) | set(rf)):
                rel = "both" if name in cf and name in rf else "condition" if name in cf else "requirement"
                edges.append({"id": f"{name}->{r.id}", "source": name, "target": r.id, "relation": rel,
                              "contradiction_evidence": name in because.get(r.id, ())})
            if status != "inactive":
                edges.append({"id": f"{r.id}->verdict", "source": r.id, "target": "verdict", "relation": "outcome",
                              "contradiction_evidence": status == "violated"})
    nodes.append({"id": "verdict", "kind": "verdict", "label": "Verdict", "status": case["verdict"]})
    editable = [{"name": n, "label": LABEL.get(n, n), "kind": s.kind, "values": list(s.values) if s.values else None,
                 "lo": s.lo, "hi": s.hi} for n, s in FACTS.items() if not s.derived]
    return {"case_id": case["case_id"], "policy_version": case["policy_version"], "facts_hash": _hash(values),
            "base_facts_hash": base_hash, "preview": preview, "saved_verdict": saved_verdict, "verdict": case["verdict"],
            "nodes": nodes, "edges": edges, "editable_fields": editable, "questions": case["questions"], "fix": case["fix"]}


class PreviewIn(BaseModel):
    overrides: dict[str, Any] = {}
    base_facts_hash: str


@router.get("/cases/{case_id}/graph")
def get_graph(case_id: str):
    with closing(db.connect()) as conn:
        c = cases._get(conn, case_id)
    return graph(c, False, c["verdict"], set(), _hash({n: f["value"] for n, f in c["facts"].items()}))


@router.post("/cases/{case_id}/graph/preview")
def preview_graph(case_id: str, body: PreviewIn):
    with closing(db.connect()) as conn:
        c = cases._get(conn, case_id)
    saved = {n: f["value"] for n, f in c["facts"].items()}
    if _hash(saved) != body.base_facts_hash:
        raise HTTPException(409, "saved facts changed; reload the case")
    facts = {n: v for n, v in saved.items() if not FACTS[n].derived}  # derived facts are recomputed by the rules
    sources = {n: c["facts"][n]["source"] for n in facts}
    for name, value in body.overrides.items():
        if name not in FACTS or FACTS[name].derived:
            raise HTTPException(422, f"{name} cannot be overridden")
        if value is None:
            facts.pop(name, None)
            continue
        try:
            facts[name] = validate_value(name, value)
        except ValueError as e:
            raise HTTPException(422, str(e))
        sources[name] = "preview"
    probs = c.get("_inputs", {}).get("probs", {})
    pc = cases.to_case(c["case_id"], c["created_at"], c["employee_id"], c["text"], cases.POLICY.decide(facts, probs),
                       sources, probs, None, None)
    return graph(pc, True, c["verdict"], set(body.overrides), body.base_facts_hash)
