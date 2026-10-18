import hashlib
import json
import math
import operator
import os
import threading
from pathlib import Path
from typing import Literal, NamedTuple

import z3

from engine.schema import FACTS

# Z3's shared context is not thread-safe; FastAPI serves sync routes from a thread pool.
ENGINE_LOCK = threading.RLock()


def _locked(fn, *args):
    """Run fn under ENGINE_LOCK so its Z3 temporaries are freed before the lock is released.
    On error, drop the traceback (which pins fn's frame and its Z3 locals) while still locked."""
    with ENGINE_LOCK:
        try:
            return fn(*args)
        except Exception as e:
            raise e.with_traceback(None) from None

_CMP = {"eq": operator.eq, "neq": operator.ne, "gt": operator.gt, "ge": operator.ge, "lt": operator.lt, "le": operator.le}
_MAKE = {"enum": z3.Int, "int": z3.Int, "real": z3.Real, "bool": z3.Bool}


class Rule(NamedTuple):
    id: str
    layer: str
    text: str
    when: z3.BoolRef
    require: z3.BoolRef
    formula: z3.BoolRef
    raw: dict


class Violation(NamedTuple):
    rule: str
    because: list[str]


class Verdict(NamedTuple):
    status: Literal["compliant", "violation", "undetermined"]
    violations: list[Violation]
    applied: list[str]


class FixStep(NamedTuple):
    fact: str
    from_: object
    to: object


class Decision(NamedTuple):
    facts: dict
    derived: dict[str, str]
    verdict: Verdict
    fix: list[FixStep] | None  # [] when nothing to fix, None = no change you control makes this compliant
    questions: list[str]


def _p(entry) -> float | None:
    p = entry.get("p") if isinstance(entry, dict) else None
    return float(p) if isinstance(p, (int, float)) and not isinstance(p, bool) and math.isfinite(p) else None


def facts_from_probs(probs: dict[str, dict], hi: float | None = None, lo: float | None = None) -> dict[str, object]:
    """Jev's per-fact probabilities -> the facts known with confidence. Pure Python, no Z3."""
    hi = float(os.environ.get("POP_P_HI", 0.85)) if hi is None else hi
    lo = float(os.environ.get("POP_P_LO", 0.15)) if lo is None else lo
    facts = {}
    for name, entry in probs.items():
        spec, p = FACTS.get(name), _p(entry)
        if spec is None or p is None:
            continue
        if spec.kind == "enum" and entry.get("value") in spec.values and p >= hi:
            facts[name] = entry["value"]
        elif spec.kind == "bool" and (p >= hi or p <= lo):
            facts[name] = p >= hi
    return facts


def _sat(*constraints) -> bool:
    s = z3.Solver()
    s.add(*constraints)
    return s.check() == z3.sat


def to_z3(name: str, value) -> z3.ExprRef:
    """Returns a Z3 term: callers must hold ENGINE_LOCK."""
    spec = FACTS[name]
    if spec.kind == "enum":
        if value not in spec.values:
            raise ValueError(f"{name}: unknown value {value!r}")
        return z3.IntVal(spec.values.index(value))
    if spec.kind == "bool":
        return z3.BoolVal(value)
    if spec.kind == "real":
        return z3.RealVal(str(value))
    return z3.IntVal(value)


def from_z3(name: str, v: z3.ExprRef) -> object:
    """Takes a Z3 value: callers must hold ENGINE_LOCK."""
    spec = FACTS[name]
    if spec.kind == "enum":
        return spec.values[v.as_long()]
    if spec.kind == "bool":
        return z3.is_true(v)
    if spec.kind == "real":
        return float(v.as_fraction())
    return v.as_long()


def compile_expr(expr, vars: dict[str, z3.ExprRef]) -> z3.ExprRef:
    """Returns a Z3 term: callers must hold ENGINE_LOCK."""
    if isinstance(expr, bool):
        return z3.BoolVal(expr)
    if isinstance(expr, str):  # bare bool fact name
        if FACTS[expr].kind != "bool":
            raise ValueError(f"{expr}: not a bool fact")
        return vars[expr]
    (op, arg), = expr.items()
    if op == "and":
        return z3.And(*[compile_expr(e, vars) for e in arg])
    if op == "or":
        return z3.Or(*[compile_expr(e, vars) for e in arg])
    if op == "not":
        return z3.Not(compile_expr(arg, vars))
    name, lit = arg
    v = vars[name]  # unknown fact -> KeyError
    if op == "in":
        return z3.Or(*[v == to_z3(name, x) for x in lit])
    return _CMP[op](v, to_z3(name, lit))


def _names(expr) -> set[str]:
    """Fact names an expression mentions, from its raw JSON."""
    if isinstance(expr, bool):
        return set()
    if isinstance(expr, str):
        return {expr}
    (op, arg), = expr.items()
    if op in ("and", "or"):
        return set().union(*map(_names, arg))
    if op == "not":
        return _names(arg)
    return {arg[0]}


class Policy:
    # Every public method is `return _locked(self._name, ...)`; the private _name does all Z3 work.
    # Public return values are plain Python (facts_eq is the documented exception).
    def __init__(self, rules: list[dict]):
        _locked(self._compile, rules)

    def __del__(self):
        # this object's Z3 terms are dec_ref'd here, so drop them under the lock too
        with ENGINE_LOCK:
            self.__dict__.clear()

    def _compile(self, rules: list[dict]) -> None:
        self.vars = {name: _MAKE[s.kind](name) for name, s in FACTS.items()}
        self.dom = []
        for name, s in FACTS.items():
            v = self.vars[name]
            if s.kind == "enum":
                self.dom.append(z3.And(v >= 0, v < len(s.values)))
            if s.lo is not None:
                self.dom.append(v >= s.lo)
            if s.hi is not None:
                self.dom.append(v <= s.hi)
        self.rules = []
        for r in rules:
            when, require = compile_expr(r["when"], self.vars), compile_expr(r["require"], self.vars)
            self.rules.append(Rule(r["id"], r["layer"], r["text"], when, require, z3.Implies(when, require), r))
        self.by_id = {r.id: r for r in self.rules}
        self.when_names = [_names(r["when"]) for r in rules]
        self.formula_names = [w | _names(r["require"]) for w, r in zip(self.when_names, rules)]
        self.track = {n: z3.Bool(f"fact_{n}") for n in FACTS}
        self.all_formulas = z3.And(*[r.formula for r in self.rules])
        self.version = hashlib.sha256(json.dumps(rules, sort_keys=True).encode()).hexdigest()[:12]

    def facts_eq(self, facts: dict) -> dict[str, z3.BoolRef]:
        """name -> `var == value`. Returns Z3 terms: callers must hold ENGINE_LOCK while they hold the result."""
        return _locked(self._facts_eq, facts)

    def _facts_eq(self, facts: dict) -> dict[str, z3.BoolRef]:
        return {n: self.vars[n] == to_z3(n, v) for n, v in facts.items()}

    def check(self, facts: dict[str, object]) -> Verdict:
        return _locked(self._check, facts)

    def _check(self, facts: dict[str, object]) -> Verdict:
        eqs = self._facts_eq(facts)
        s = z3.Solver()
        s.add(*self.dom, *eqs.values())
        # One model fixing the known facts: a rule whose facts are all known is decided by eval, no solver.
        # Joint check first: sat means no rule is violated on its own, so the per-rule loop is skipped.
        joint = s.check(self.all_formulas) == z3.sat
        m = s.model() if joint or s.check() == z3.sat else None  # None: a known fact is outside its domain
        if not joint:
            violations = []
            for r, names in zip(self.rules, self.formula_names):
                if m is not None and names <= facts.keys():
                    holds = z3.is_true(m.eval(r.formula, model_completion=True))
                else:
                    holds = s.check(r.formula) == z3.sat
                if holds:
                    continue
                # fails: only now pay for the minimized core (fresh solver, so cores match the per-rule spec)
                c = z3.Solver()
                c.set(unsat_core=True)
                c.set("core.minimize", True)
                c.add(*self.dom, r.formula)
                for n, eq in eqs.items():
                    c.assert_and_track(eq, self.track[n])
                c.check()
                violations.append(Violation(r.id, sorted(str(b).removeprefix("fact_") for b in c.unsat_core())))
            if violations:
                return Verdict("violation", violations, [])
        if s.check(z3.Not(self.all_formulas)) == z3.sat:
            return Verdict("undetermined", [], [])
        applied = []
        for r, names in zip(self.rules, self.when_names):
            if (z3.is_true(m.eval(r.when, model_completion=True)) if m is not None and names <= facts.keys()
                    else s.check(z3.Not(r.when)) == z3.unsat):
                applied.append(r.id)
        return Verdict("compliant", [], applied)

    def required_values(self, facts: dict, fact: str) -> list[str]:
        return _locked(self._required_values, facts, fact)

    def _required_values(self, facts: dict, fact: str) -> list[str]:
        # only rules mentioning the fact, so a violation elsewhere can't hide the required value
        s = z3.Solver()
        s.add(*self.dom, *[r.formula for r in self.rules if fact in json.dumps(r.raw)], *self._facts_eq(facts).values())
        out = []
        for i, v in enumerate(FACTS[fact].values):
            s.push()
            s.add(self.vars[fact] == i)
            if s.check() == z3.sat:
                out.append(v)
            s.pop()
        return out

    def resolve(self, facts: dict) -> tuple[dict, dict[str, str]]:
        return _locked(self._resolve, facts)

    def _resolve(self, facts: dict) -> tuple[dict, dict[str, str]]:
        out, derived = dict(facts), {}
        eqs = list(self._facts_eq(facts).values())
        for name, spec in FACTS.items():
            if not spec.derived or name in facts:
                continue
            vals = self._required_values(facts, name)
            if len(vals) != 1:
                continue
            out[name] = vals[0]
            for r in self.rules:
                if name in json.dumps(r.raw) and not _sat(*self.dom, *eqs, z3.Not(r.when)):
                    derived[name] = r.id
                    break
        return out, derived

    def questions(self, facts: dict, probs: dict[str, dict]) -> list[str]:
        return _locked(self._questions, facts, probs)

    def _questions(self, facts: dict, probs: dict[str, dict]) -> list[str]:
        def outcome(f):
            rf, _ = self._resolve(f)
            v = self._check(rf)
            return v.status, {x.rule for x in v.violations}, {n: rf.get(n) for n, s in FACTS.items() if s.derived}

        asked = [n for n, s in FACTS.items() if s.kind == "bool" and n not in facts
                 and outcome({**facts, n: True}) != outcome({**facts, n: False})]
        # stable sort: ties keep schema order
        def doubt(n):
            p = _p(probs.get(n))
            return abs((0.5 if p is None else p) - 0.5)
        return sorted(asked, key=doubt)

    def fix(self, facts: dict) -> list[FixStep] | None:
        return _locked(self._fix, facts)

    def _fix(self, facts: dict) -> list[FixStep] | None:
        eqs = self._facts_eq(facts)
        hard = [*self.dom, *[r.formula for r in self.rules]] + [eqs[n] for n in facts if not FACTS[n].mutable]
        mutable = [n for n in FACTS if n in facts and FACTS[n].mutable]  # unknown facts stay free
        o = z3.Optimize()
        o.add(*hard)
        for n in mutable:
            o.add_soft(eqs[n], weight=FACTS[n].weight)
        if o.check() != z3.sat:
            return None
        m = o.model()
        new = {n: from_z3(n, m.eval(self.vars[n], model_completion=True)) for n in mutable}
        changed = sorted((n for n in mutable if new[n] != facts[n]), key=lambda n: -FACTS[n].weight)  # stable: schema order
        if "amount" in changed:
            # whole cents close an open bound: `amount < 75` gives 74.99, not Z3's "75 - epsilon"
            o2 = z3.Optimize()
            cents = z3.Int("cents")
            o2.add(*hard, *[self.vars[n] == to_z3(n, new[n]) for n in mutable if n != "amount"],
                   self.vars["amount"] <= to_z3("amount", facts["amount"]), self.vars["amount"] * 100 == cents)
            o2.maximize(cents)
            if o2.check() == z3.sat:
                new["amount"] = o2.model()[cents].as_long() / 100
        return [FixStep(n, facts[n], new[n]) for n in changed]

    def decide(self, facts: dict, probs: dict[str, dict]) -> Decision:
        return _locked(self._decide, facts, probs)

    def _decide(self, facts: dict, probs: dict[str, dict]) -> Decision:
        rf, derived = self._resolve(facts)
        verdict = self._check(rf)
        fix = self._fix(rf) if verdict.status == "violation" else []
        questions = self._questions(rf, probs) if verdict.status == "undetermined" else []
        return Decision(rf, derived, verdict, fix, questions)

    def facts_from_model(self, model: z3.ModelRef) -> dict[str, object]:
        """Every fact's value in a Z3 model. Takes a Z3 model: callers must hold ENGINE_LOCK."""
        return _locked(self._facts_from_model, model)

    def _facts_from_model(self, model: z3.ModelRef) -> dict[str, object]:
        return {n: from_z3(n, model.eval(v, model_completion=True)) for n, v in self.vars.items()}

    def applicable(self, facts: dict) -> list[dict]:
        return _locked(self._applicable, facts)

    def _applicable(self, facts: dict) -> list[dict]:
        """A person's standing facts (role, tenure_days) -> every rule with whether it can still fire for them,
        and, for a rule that only holds while tenure_days is below a bound, how many more days it applies."""
        eqs = self._facts_eq(facts)
        out = []
        for r in self.rules:
            fires = _sat(*self.dom, *eqs.values(), r.when)
            days_left = None
            if fires and "tenure_days" in facts and "tenure_days" in _names(r.raw["when"]):
                t = self.vars["tenure_days"]
                o = z3.Optimize()
                o.add(*self.dom, *[eq for n, eq in eqs.items() if n != "tenure_days"], r.when, t >= facts["tenure_days"])
                h = o.maximize(t)
                if o.check() == z3.sat and z3.is_int_value(o.upper(h)):  # bounded: the rule stops holding past this day
                    days_left = o.upper(h).as_long() - facts["tenure_days"] + 1
            out.append({"id": r.id, "layer": r.layer, "text": r.text, "applies": fires, "days_left": days_left})
        return out

    def audit(self) -> dict:
        return _locked(self._audit)

    def _audit(self) -> dict:
        s = z3.Solver()
        s.add(*self.dom)
        dead = [r.id for r in self.rules if not _sat(*self.dom, r.when)]
        live = [r for r in self.rules if r.id not in dead]
        conflicts = []
        # ponytail: O(n^2) pairs with push/pop on one solver; ~300 pairs for the shipped packs
        for i, a in enumerate(live):
            for b in live[i + 1:]:
                s.push()
                s.add(a.when, b.when)
                if s.check() == z3.sat:
                    model = s.model()
                    # a prohibition (require false) is never "in conflict" with a rule it already rules out
                    if s.check(a.require) == z3.sat and s.check(b.require) == z3.sat and s.check(a.require, b.require) == z3.unsat:
                        conflicts.append({"a": a.id, "b": b.id, "example": self._facts_from_model(model)})
                s.pop()
        return {"dead": dead, "conflicts": conflicts}

    def disagreement(self, rule_a: dict, rule_b: dict) -> dict | None:
        return _locked(self._disagreement, rule_a, rule_b)

    def _disagreement(self, rule_a: dict, rule_b: dict) -> dict | None:
        fa, fb = (z3.Implies(compile_expr(r["when"], self.vars), compile_expr(r["require"], self.vars)) for r in (rule_a, rule_b))
        s = z3.Solver()
        s.add(*self.dom, fa != fb)
        return self._facts_from_model(s.model()) if s.check() == z3.sat else None


def load_policy(*paths: str | Path) -> Policy:
    rules = []
    for p in paths:
        rules += json.loads(Path(p).read_text())
    return Policy(rules)
