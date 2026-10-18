"""Independent three-valued (true/false/unknown) interpreter over the rule JSON. No Z3.

Used only to compute gold verdicts for the held-out set; it shares no code with engine/rules.py.
A fact missing from `facts` is unknown. Unknown propagates Kleene-style through and/or/not/compare.
"""
import operator

_CMP = {"eq": operator.eq, "neq": operator.ne, "gt": operator.gt, "ge": operator.ge, "lt": operator.lt, "le": operator.le}


def ev(expr, facts: dict):
    """-> True, False or None (unknown)."""
    if isinstance(expr, bool):
        return expr
    if isinstance(expr, str):
        return facts.get(expr)
    (op, arg), = expr.items()
    if op in ("and", "or"):
        vals = [ev(e, facts) for e in arg]
        short = op == "or"  # the value that decides the connective on its own
        return short if short in vals else (None if None in vals else not short)
    if op == "not":
        v = ev(arg, facts)
        return None if v is None else not v
    name, lit = arg
    if isinstance(name, dict):  # {"per": [fact, by]}: fact / by
        fact, by = name["per"]
        if fact not in facts or by not in facts:
            return None
        return _CMP[op](facts[fact] / facts[by], lit)
    if name not in facts:
        return None
    return facts[name] in lit if op == "in" else _CMP[op](facts[name], lit)


def coded_account(expense_kind: str | None, at_company_event) -> str | None:
    """The IRS pack's coding, written out by hand (the derived fact Z3 would force)."""
    if expense_kind is None or (expense_kind == "meal" and at_company_event is None):
        return None
    if expense_kind == "meal":
        return "meals_100" if at_company_event else "meals_50"
    return {"entertainment": "entertainment_0", "rideshare": "travel", "airfare": "travel", "hotel": "travel",
            "software": "office", "equipment": "office"}.get(expense_kind, "other")


def verdict(rules: list[dict], facts: dict) -> tuple[str, list[str]]:
    """-> ("violation", [rule ids]) | ("undetermined", []) | ("compliant", [])."""
    violated, unknown = [], False
    for r in rules:
        w, q = ev(r["when"], facts), ev(r["require"], facts)
        if w is True and q is False:
            violated.append(r["id"])
        elif w is not False and q is not True and (w is None or q is None):
            unknown = True
    if violated:
        return "violation", violated
    return ("undetermined", []) if unknown else ("compliant", [])


if __name__ == "__main__":  # self-check: python -m eval.gold
    R = [{"id": "a", "when": {"gt": ["amount", 35]}, "require": "pre_approved"},
         {"id": "b", "when": {"and": [{"eq": ["role", "intern"]}, {"eq": ["expense_kind", "meal"]}]}, "require": "at_company_event"}]
    assert verdict(R, {"amount": 48, "pre_approved": False, "role": "employee", "expense_kind": "meal"}) == ("violation", ["a"])
    assert verdict(R, {"amount": 48, "pre_approved": True, "role": "employee", "expense_kind": "meal"}) == ("compliant", [])
    assert verdict(R, {"amount": 48, "pre_approved": True, "role": "intern", "expense_kind": "meal"}) == ("undetermined", [])
    assert verdict(R, {"amount": 48, "role": "employee", "expense_kind": "meal"}) == ("undetermined", [])
    assert verdict(R, {"amount": 20, "expense_kind": "meal"}) == ("undetermined", [])  # role unknown, b may fire
    assert verdict(R, {"amount": 20, "role": "employee", "expense_kind": "hotel"}) == ("compliant", [])
    assert coded_account("meal", True) == "meals_100" and coded_account("meal", None) is None and coded_account("other", False) == "other"
    print("gold.py ok")
