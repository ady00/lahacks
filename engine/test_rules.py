import z3, pytest
from engine.rules import Policy, compile_expr, load_policy, to_z3
from engine.schema import validate_value
RULE_5_2 = {"id": "5.2", "layer": "company",
  "text": "Interns get no transport reimbursement except at company events.",
  "when": {"and": [{"eq": ["role", "intern"]}, {"in": ["expense_kind", ["rideshare", "airfare"]]}]},
  "require": "at_company_event"}

def test_compiles_rule_5_2_and_it_bites():
    p = Policy([RULE_5_2])
    assert p.rules[0].id == "5.2" and p.rules[0].layer == "company"
    s = z3.Solver(); s.add(*p.dom, p.rules[0].formula)
    s.add(p.vars["role"] == to_z3("role", "intern"), p.vars["expense_kind"] == to_z3("expense_kind", "rideshare"), p.vars["at_company_event"] == False)
    assert s.check() == z3.unsat

def test_require_may_be_an_expression_or_false():
    p = Policy([{"id": "x", "layer": "irs", "text": "t", "when": {"eq": ["expense_kind", "meal"]}, "require": {"eq": ["coded_account", "meals_50"]}},
                {"id": "y", "layer": "company", "text": "t", "when": {"eq": ["role", "contractor"]}, "require": False}])
    assert len(p.rules) == 2

def test_bool_literal_comparison_compiles():
    p = Policy([{"id": "6.5", "layer": "company", "text": "t",
                 "when": {"and": [{"eq": ["expense_kind", "meal"]}, {"eq": ["client_present", True]}, {"gt": ["amount", 150]}]},
                 "require": "pre_approved"}])
    s = z3.Solver(); s.add(*p.dom, p.all_formulas)
    s.add(p.vars["expense_kind"] == to_z3("expense_kind", "meal"), p.vars["client_present"] == True,
          p.vars["amount"] == to_z3("amount", 200.0), p.vars["pre_approved"] == False)
    assert s.check() == z3.unsat

def test_unknown_fact_and_value_raise():
    p = Policy([])
    with pytest.raises(KeyError): compile_expr({"eq": ["colour", "red"]}, p.vars)
    with pytest.raises(ValueError): compile_expr({"eq": ["role", "ceo"]}, p.vars)

def test_version_is_12_hex_and_stable():
    a, b = Policy([RULE_5_2]), Policy([RULE_5_2])
    assert a.version == b.version and len(a.version) == 12

def test_load_policy_reads_both_packs():
    p = load_policy("engine/demo_policy.json", "engine/irs_pack.json")
    assert {"3.4", "5.2", "IRS-meal"} <= set(p.by_id)

def test_validate_value():
    assert validate_value("amount", 12) == 12.0 and validate_value("hour", 3.0) == 3
    assert validate_value("role", "intern") == "intern" and validate_value("pre_approved", False) is False
    with pytest.raises(KeyError): validate_value("colour", "red")
    for name, bad in [("amount", -1), ("amount", 0), ("amount", True), ("hour", 99), ("hour", 2.5),
                      ("days_since_purchase", -1), ("expense_kind", "snack"), ("pre_approved", 1), ("role", 3)]:
        with pytest.raises(ValueError): validate_value(name, bad)

# reviewer edge cases
import json
from concurrent.futures import ThreadPoolExecutor
from engine.rules import from_z3
from engine.schema import FACTS

def test_reviewer_round_trip_every_kind_and_empty_policy():
    p = Policy([])
    s = z3.Solver(); s.add(*p.dom, p.all_formulas); assert s.check() == z3.sat
    for n, v in [("role", "intern"), ("coded_account", "other"), ("amount", 74.99), ("amount", 48), ("amount", 0.1),
                 ("hour", 0), ("days_since_purchase", 61), ("pre_approved", False), ("client_present", True)]:
        s = z3.Solver(); s.add(p.vars[n] == to_z3(n, v)); assert s.check() == z3.sat
        assert from_z3(n, s.model().eval(p.vars[n], model_completion=True)) == v
    assert z3.simplify(to_z3("amount", 0.1) == z3.Q(1, 10))
    assert list(FACTS)[:4] == ["role", "expense_kind", "coded_account", "amount"] and list(FACTS)[-1] == "at_company_event"

def _bites(p, rid, **facts):
    s = z3.Solver(); s.add(*p.dom, p.by_id[rid].formula)
    s.add(*[p.vars[k] == to_z3(k, v) for k, v in facts.items()])
    return s.check() == z3.unsat

def test_reviewer_thresholds_exact_and_irs_coding():
    p = load_policy("engine/demo_policy.json", "engine/irs_pack.json")
    assert not _bites(p, "3.4", amount=35, pre_approved=False) and _bites(p, "3.4", amount=35.01, pre_approved=False)
    assert not _bites(p, "IRS-receipt-60", days_since_purchase=60, receipt_attached=False)
    assert _bites(p, "IRS-receipt-60", days_since_purchase=61, receipt_attached=False)
    assert _bites(p, "IRS-meal", expense_kind="meal", at_company_event=False, coded_account="meals_100")
    assert _bites(p, "IRS-meal-event", expense_kind="meal", at_company_event=True, coded_account="meals_50")
    assert not _bites(p, "IRS-meal", expense_kind="meal", at_company_event=True, coded_account="meals_100")

def test_reviewer_raw_version_unicode_and_threads():
    p = load_policy("engine/demo_policy.json", "engine/irs_pack.json")
    assert "pre_approved" in json.dumps(p.by_id["3.4"].raw) and "at_company_event" in json.dumps(p.by_id["IRS-meal"].raw)
    assert p.version == load_policy("engine/demo_policy.json", "engine/irs_pack.json").version
    assert p.version != load_policy("engine/irs_pack.json", "engine/demo_policy.json").version
    u = Policy([{"id": "ü", "layer": "company", "text": "Café ☕ über $35", "when": {"gt": ["amount", 35]}, "require": "pre_approved"}])
    assert len(u.version) == 12 and u.by_id["ü"].text.startswith("Café")
    with ThreadPoolExecutor(8) as ex:
        versions = set(ex.map(lambda _: load_policy("engine/demo_policy.json", "engine/irs_pack.json").version, range(32)))
    assert versions == {p.version}

# Task 3: check()
DINNER = dict(role="employee", expense_kind="meal", client_present=True, at_company_event=False,
              amount=48, hour=19, days_since_purchase=0, pre_approved=False, coded_account="travel")
P = load_policy("engine/demo_policy.json", "engine/irs_pack.json")

def test_dinner_breaks_two_rules_and_cites_facts():
    v = P.check(DINNER)
    assert v.status == "violation"
    by = {x.rule: x.because for x in v.violations}
    assert by["3.4"] == ["amount", "pre_approved"]
    assert set(by["IRS-meal"]) == {"expense_kind", "at_company_event", "coded_account"}

def test_cheap_coded_dinner_is_proven_compliant():
    v = P.check({**DINNER, "amount": 30, "coded_account": "meals_50"})
    assert v.status == "compliant" and "IRS-meal" in v.applied and "3.4" not in v.applied

def test_unknown_pre_approval_is_undetermined():
    f = {k: v for k, v in DINNER.items() if k != "pre_approved"}
    assert P.check({**f, "coded_account": "meals_50"}).status == "undetermined"

def test_check_order_unknown_fact_and_applied_via_solver():
    v = P.check(DINNER)
    assert [x.rule for x in v.violations] == ["3.4", "IRS-meal"] and v.applied == []
    assert P.check({}).status == "undetermined"
    with pytest.raises(KeyError): P.check({"colour": "red"})
    # amount unknown, pre_approved settles 3.4 anyway: compliant, and the solver says 3.4 need not apply
    v = P.check({**{k: x for k, x in DINNER.items() if k != "amount"}, "pre_approved": True, "coded_account": "meals_50"})
    assert v.status == "compliant" and "3.4" not in v.applied and "IRS-meal" in v.applied
    # hour unknown but its domain forces the condition: applied through the solver
    p = Policy([{"id": "h", "layer": "company", "text": "t", "when": {"ge": ["hour", 0]}, "require": True}])
    assert p.check({}).applied == ["h"]


def test_reviewer_check_cores_deterministic_and_joint_shortcut_matches_naive():
    import random
    from engine.schema import FACTS

    def naive(p, facts):
        eqs = {n: p.vars[n] == to_z3(n, v) for n, v in facts.items()}
        out = []
        for r in p.rules:
            s = z3.Solver(); s.set(unsat_core=True); s.set("core.minimize", True); s.add(*p.dom, r.formula)
            for n, e in eqs.items(): s.assert_and_track(e, z3.Bool(f"fact_{n}"))
            if s.check() == z3.unsat: out.append((r.id, set(str(b)[5:] for b in s.unsat_core())))
        if out: return "violation", out
        s = z3.Solver(); s.add(*p.dom, *eqs.values(), z3.Not(p.all_formulas))
        return ("undetermined" if s.check() == z3.sat else "compliant"), []

    rng = random.Random(7)
    for _ in range(120):
        f = {}
        for n, s in FACTS.items():
            if rng.random() < 0.8:
                f[n] = (rng.choice(s.values) if s.kind == "enum" else rng.random() < 0.5 if s.kind == "bool"
                        else rng.choice([10, 35, 35.01, 48]) if n == "amount" else rng.choice([0, 22, 61]) if n == "days_since_purchase"
                        else rng.choice([5, 19, 22]))
        v = P.check(f)
        assert (v.status, [(x.rule, set(x.because)) for x in v.violations]) == naive(P, f)
        assert all(x.because == sorted(x.because) for x in v.violations)
    assert len({repr(load_policy("engine/demo_policy.json", "engine/irs_pack.json").check(DINNER)) for _ in range(10)}) == 1


def test_reviewer_check_combination_only_and_out_of_domain():
    # each IRS meal rule is satisfiable alone (event unknown), but not jointly: undetermined, no violations
    f = {k: v for k, v in DINNER.items() if k != "at_company_event"}
    v = P.check({**f, "amount": 20})
    assert v.status == "undetermined" and v.violations == []
    # a value outside its domain makes every rule unsat, citing that fact (why the API must 422 first)
    v = P.check({**DINNER, "hour": 99})
    assert v.status == "violation" and [x.rule for x in v.violations] == [r.id for r in P.rules]
    assert all(x.because == ["hour"] for x in v.violations)


def test_reviewer_check_empty_policy_and_amount_threshold():
    assert Policy([]).check(DINNER) == ("compliant", [], [])
    v = P.check({**DINNER, "amount": 35, "coded_account": "meals_50"})  # exactly on 3.4's threshold: not over $35
    assert v.status == "compliant" and "3.4" not in v.applied
    v = P.check({**DINNER, "amount": 35.01, "coded_account": "meals_50"})
    assert [x.rule for x in v.violations] == ["3.4"]


def test_concurrent_check_does_not_crash():
    # subprocess: a segfault from a Z3 refcount race fails this test instead of killing pytest
    code = """
from concurrent.futures import ThreadPoolExecutor
from engine.rules import load_policy
from engine.test_rules import DINNER, ENT
P = load_policy("engine/demo_policy.json", "engine/irs_pack.json")
ok = {**DINNER, "amount": 30, "coded_account": "meals_50"}
def run(i):
    return [repr(P.check(DINNER if (i + k) % 2 else ok)) for k in range(200)] + \
           [repr(P.decide({k: v for k, v in (DINNER if (i + k) % 2 else ok).items() if k != "coded_account"}, {})) for k in range(50)] + \
           [repr(P.decide(DINNER if (i + k) % 2 else ENT, {})) for k in range(20)]
with ThreadPoolExecutor(8) as ex:
    out = list(ex.map(run, range(8)))
assert len({tuple(sorted(set(o))) for o in out}) == 1 and len(set(out[0])) == 6, out[0][:2]
"""
    import subprocess, sys
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, (r.returncode, r.stderr[-2000:])


# Task 4: facts_from_probs, required_values, resolve, questions, decide
from engine.rules import facts_from_probs

def test_facts_from_probs_thresholds():
    probs = {"expense_kind": {"value": "meal", "p": 0.97}, "client_present": {"p": 0.91},
             "at_company_event": {"p": 0.08}, "receipt_attached": {"p": 0.5}}
    assert facts_from_probs(probs) == {"expense_kind": "meal", "client_present": True, "at_company_event": False}

def test_facts_from_probs_env_and_bad_entries(monkeypatch):
    probs = {"client_present": {"p": 0.8}, "colour": {"p": 1.0}, "role": {"value": "ceo", "p": 0.99},
             "pre_approved": {}, "receipt_attached": {"p": "high"}, "expense_kind": {"value": "meal", "p": True},
             "amount": {"value": 12, "p": 0.99}, "hour": None}
    assert facts_from_probs(probs) == {}
    monkeypatch.setenv("POP_P_HI", "0.75")
    assert facts_from_probs(probs) == {"client_present": True}
    assert facts_from_probs({"client_present": {"p": 0.85}, "at_company_event": {"p": 0.15}}, hi=0.9, lo=0.1) == {}

UNCODED = {k: v for k, v in DINNER.items() if k != "coded_account"}

def test_required_account_for_a_client_dinner_is_meals_50():
    assert P.required_values(UNCODED, "coded_account") == ["meals_50"]
    unknown_event = {k: v for k, v in UNCODED.items() if k != "at_company_event"}
    assert P.required_values(unknown_event, "coded_account") == ["meals_50", "meals_100"]

def test_resolve_sets_the_account_and_names_the_rule():
    facts, derived = P.resolve(UNCODED)
    assert facts["coded_account"] == "meals_50" and derived == {"coded_account": "IRS-meal"}

def test_resolve_leaves_ambiguous_and_given_accounts_alone():
    unknown_event = {k: v for k, v in UNCODED.items() if k != "at_company_event"}
    assert P.resolve(unknown_event) == (unknown_event, {})
    assert P.resolve(DINNER) == (DINNER, {})  # already coded (wrongly): resolve never overrides
    assert P.resolve({}) == ({}, {})

def test_question_is_asked_only_when_it_decides():
    ride = dict(role="intern", expense_kind="rideshare", amount=20, hour=9, days_since_purchase=0, pre_approved=True)
    assert P.questions(ride, {"at_company_event": {"p": 0.4}}) == ["at_company_event"]
    assert P.questions({k: v for k, v in UNCODED.items() if k != "client_present"}, {}) == []  # 3.4 broken either way

def test_questions_sorted_by_uncertainty():
    f = dict(role="intern", expense_kind="rideshare", amount=48, hour=9, days_since_purchase=61)
    probs = {"at_company_event": {"p": 0.2}, "pre_approved": {"p": 0.6}, "receipt_attached": {"p": "?"}}
    assert P.questions(f, probs) == ["receipt_attached", "pre_approved", "at_company_event"]

def test_decide_on_the_demo_dinner():
    d = P.decide(UNCODED, {})
    assert d.facts["coded_account"] == "meals_50" and d.derived == {"coded_account": "IRS-meal"}
    assert d.verdict.status == "violation" and [v.rule for v in d.verdict.violations] == ["3.4"]
    assert d.fix == [FixStep("pre_approved", False, True)] and d.questions == []

def test_decide_compliant_and_undetermined():
    d = P.decide({**UNCODED, "amount": 30}, {})
    assert d.verdict.status == "compliant" and d.fix == [] and d.questions == []
    ride = dict(role="intern", expense_kind="rideshare", amount=20, hour=9, days_since_purchase=0, pre_approved=True)
    d = P.decide(ride, {})
    assert d.verdict.status == "undetermined" and d.questions == ["at_company_event"] and d.fix == []
    assert d.facts == {**ride, "coded_account": "travel"} and d.derived == {"coded_account": "IRS-travel"}


# reviewer edge cases (Task 4)
def test_reviewer_decide_on_the_threshold_repeated_and_not_aliased():
    at = {**UNCODED, "amount": 35}
    d1, d2 = P.decide(at, {}), P.decide(at, {})
    assert d1 == d2 and d1.verdict.status == "compliant" and d1.facts["coded_account"] == "meals_50"
    d1.facts["amount"] = 999
    assert at["amount"] == 35 and "coded_account" not in at  # input never mutated, result never aliased
    v = P.decide({**UNCODED, "amount": 35.01}, {})
    assert v.verdict.status == "violation" and [x.rule for x in v.verdict.violations] == ["3.4"]

def test_reviewer_facts_from_probs_odd_entries():
    assert facts_from_probs({}) == {}
    probs = {"café": {"p": 1.0}, "expense_kind": {"value": ["meal"], "p": 0.99}, "role": {"value": {}, "p": 0.99},
             "client_present": {"p": float("nan")}, "receipt_attached": {"p": float("inf")},
             "pre_approved": {"p": 1}, "at_company_event": {"p": 0}}
    assert facts_from_probs(probs) == {"pre_approved": True, "at_company_event": False}

def test_reviewer_decide_empty_facts_and_nan_probs():
    d = P.decide({}, {})
    assert d.verdict.status == "undetermined" and d.derived == {} and d.fix == [] and d.facts == {}
    f = dict(role="intern", expense_kind="rideshare", amount=48, hour=9, days_since_purchase=61)
    probs = {"receipt_attached": {"p": float("nan")}, "pre_approved": {"p": 0.0}, "at_company_event": {"p": 0.5}}
    assert P.questions(f, probs) == ["receipt_attached", "at_company_event", "pre_approved"]


# Task 5: fix
from engine.rules import FixStep
# rule 6.4 (Task 10): entertainment over $100 is never reimbursed; pre-approval cannot help
ENT = dict(role="employee", expense_kind="entertainment", amount=150, hour=20, days_since_purchase=0,
           pre_approved=True, receipt_attached=True, coded_account="entertainment_0", client_present=True, at_company_event=False)

def test_fix_for_the_dinner_is_approval_then_recode():
    assert P.fix(DINNER) == [FixStep("pre_approved", False, True), FixStep("coded_account", "travel", "meals_50")]

def test_no_fix_when_only_immutable_facts_are_wrong():
    ride = dict(role="intern", expense_kind="rideshare", at_company_event=False, amount=20, hour=9,
                days_since_purchase=0, pre_approved=True, receipt_attached=True, coded_account="travel")
    assert P.fix(ride) is None

def test_amount_fix_reads_as_at_or_under():
    assert P.fix(ENT) == [FixStep("amount", 150, 100.0)]

def test_fix_open_bound_amount_is_whole_cents_and_plain_python():
    p = Policy([{"id": "x", "layer": "company", "text": "t", "when": {"ge": ["amount", 75]}, "require": False}])
    (step,) = p.fix({"amount": 80})
    assert step == ("amount", 80, 74.99) and type(step.to) is float
    assert p.fix({"amount": 10}) == []

def test_fix_in_decide_and_unknowns_never_reported():
    d = P.decide(ENT, {})
    assert d.verdict.status == "violation" and d.fix == [FixStep("amount", 150, 100.0)]
    assert P.decide({**DINNER, "pre_approved": True, "amount": 30}, {}).fix == [FixStep("coded_account", "travel", "meals_50")]
    ride = dict(role="intern", expense_kind="rideshare", at_company_event=False, amount=20, hour=9,
                days_since_purchase=0, pre_approved=True, receipt_attached=True)
    assert P.decide(ride, {}).fix is None
    f = {k: v for k, v in DINNER.items() if k != "pre_approved"}  # pre_approved unknown: free, not a step
    assert P.fix(f) == [FixStep("coded_account", "travel", "meals_50")]


# reviewer edge cases (Task 5)
def test_reviewer_fix_empty_inputs_and_repeat():
    assert P.fix({}) == [] and Policy([]).fix(DINNER) == []
    assert all(P.fix(DINNER) == P.fix(DINNER) for _ in range(5))
    with pytest.raises(KeyError):
        P.fix({**DINNER, "colour": "red"})

def test_reviewer_fix_amount_on_threshold_and_sub_cent():
    assert P.fix({**ENT, "amount": 100}) == []  # gt 100: exactly 100 is fine
    assert P.fix({**ENT, "amount": 100.01}) == [FixStep("amount", 100.01, 100.0)]
    assert P.fix({**ENT, "amount": 100.005}) == [FixStep("amount", 100.005, 100.0)]

def test_reviewer_fix_cheapest_across_rules_and_applied_is_never_a_violation():
    rule = lambda i, w, r: {"id": i, "layer": "company", "text": "t", "when": w, "require": r}
    p = Policy([rule("3.4", {"gt": ["amount", 35]}, "pre_approved"),
                rule("9.1", {"and": [{"eq": ["expense_kind", "rideshare"]}, {"gt": ["amount", 75]}]}, "pre_approved"),
                rule("7.2", {"and": [{"eq": ["expense_kind", "hotel"]}, {"gt": ["amount", 300]}]}, "pre_approved"),
                rule("8.2", {"and": [{"eq": ["expense_kind", "equipment"]}, {"gt": ["amount", 250]}]},
                     {"and": ["pre_approved", "receipt_attached"]})])
    base = dict(role="employee", amount=80, pre_approved=False, receipt_attached=True)
    for kind in ("rideshare", "hotel"):
        f = {**base, "expense_kind": kind}
        assert p.fix(f) == [FixStep("pre_approved", False, True)]
    eq = {**base, "expense_kind": "equipment", "amount": 300, "receipt_attached": False}
    steps = p.fix(eq)
    assert sum(FACTS[s.fact].weight for s in steps) == 3
    for f in ({**base, "expense_kind": "rideshare"}, eq, {k: v for k, v in eq.items() if k != "expense_kind"}):
        applied = {**f, **{s.fact: s.to for s in p.fix(f)}}
        assert p.check(applied).status != "violation"
