"""QuickBooks bank-rule checker: shadowed rules and overlapping pairs, via Z3 string theory."""
import z3

from engine.rules import ENGINE_LOCK

TIMEOUT_MS = 2000  # per query; unknown (timeout) reads as "not shown"


def _match(rule, d, amt, ctx):
    conds = [z3.Contains(d, z3.StringVal(w.upper(), ctx)) for w in rule["contains"]]
    if rule.get("amount_min") is not None:
        conds.append(amt >= rule["amount_min"])
    if rule.get("amount_max") is not None:
        conds.append(amt <= rule["amount_max"])
    return z3.And(conds) if conds else z3.BoolVal(True, ctx)  # empty contains + no bounds matches everything


def _solve(amt, *constraints):
    s = z3.Solver(ctx=amt.ctx)
    s.set("timeout", TIMEOUT_MS)
    s.add(amt > 0, *constraints)  # amount domain (Global Constraints): refunds/credits never reach a rule
    return s, s.check()


def _covers(xs, ys):
    """Every word of xs is a substring of some word of ys. If not, ys's words joined by a separator
    match ys and miss an xs word at any amount, so an xs rule can never contain a ys rule."""
    xs, ys = [w.upper() for w in xs], [w.upper() for w in ys]
    return all(any(x in y for y in ys) for x in xs)


def check_bank_rules(rules: list[dict]) -> dict:
    with ENGINE_LOCK:
        return _check_bank_rules(rules)  # all Z3 objects die inside, before the lock is released


def _check_bank_rules(rules):
    ctx = z3.Context()  # fresh per call: same rules give the same example, and nothing outlives the call
    d, amt = z3.String("description", ctx), z3.Real("amount", ctx)
    m = [_match(r, d, amt, ctx) for r in rules]
    shadowed, overlaps = [], []
    for j, rj in enumerate(rules):
        # only earlier rules whose words could cover j's go to Z3; unrelated merchants can't shadow j
        cand = [i for i in range(j) if _covers(rules[i]["contains"], rj["contains"])]
        if cand and _solve(amt, m[j], z3.Not(z3.Or([m[i] for i in cand])))[1] == z3.unsat:
            by = [rules[i]["id"] for i in cand if _solve(amt, m[j], z3.Not(m[i]))[1] == z3.unsat]
            shadowed.append({"rule": rj["id"], "by": by})
        for i in range(j):
            ri = rules[i]
            # noise filter before Z3: filtered pairs never reach the solver
            if ri["category"] == rj["category"] or not (_covers(ri["contains"], rj["contains"]) or _covers(rj["contains"], ri["contains"])):
                continue
            s, res = _solve(amt, m[i], m[j])
            if res == z3.sat:
                model = s.model()
                overlaps.append({"a": ri["id"], "b": rj["id"], "example": {
                    "description": model.eval(d, model_completion=True).as_string(),
                    "amount": float(model.eval(amt, model_completion=True).as_fraction())}})
    return {"shadowed": shadowed, "overlaps": overlaps}
