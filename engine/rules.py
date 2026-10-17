import hashlib
import json
import operator
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
        # Joint check first: sat means no rule is violated on its own, so the per-rule loop is skipped.
        if not _sat(*self.dom, *eqs.values(), self.all_formulas):
            violations = []
            for r in self.rules:
                s = z3.Solver()
                s.set(unsat_core=True)
                s.set("core.minimize", True)
                s.add(*self.dom, r.formula)
                for n, eq in eqs.items():
                    s.assert_and_track(eq, z3.Bool(f"fact_{n}"))
                if s.check() == z3.unsat:
                    violations.append(Violation(r.id, sorted(str(b).removeprefix("fact_") for b in s.unsat_core())))
            if violations:
                return Verdict("violation", violations, [])
        if _sat(*self.dom, *eqs.values(), z3.Not(self.all_formulas)):
            return Verdict("undetermined", [], [])
        sub = [(self.vars[n], to_z3(n, v)) for n, v in facts.items()]
        applied = []
        for r in self.rules:
            w = z3.simplify(z3.substitute(r.when, *sub)) if sub else z3.simplify(r.when)
            if z3.is_true(w) or (not z3.is_false(w) and not _sat(*self.dom, *eqs.values(), z3.Not(r.when))):
                applied.append(r.id)
        return Verdict("compliant", [], applied)


def load_policy(*paths: str | Path) -> Policy:
    rules = []
    for p in paths:
        rules += json.loads(Path(p).read_text())
    return Policy(rules)
