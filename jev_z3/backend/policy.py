"""Small JSON policy compiler with explicit partial-information semantics."""
from __future__ import annotations

import itertools
import json
from copy import deepcopy
from importlib.resources import files
from typing import Any

import z3

from .models import FACT_TYPES, EvaluationResult, Fact, LayerResult, PurchaseCase, RuleResult, digest


def load_policy_pack() -> dict:
    root = files("jev_z3.backend").joinpath("policies")
    packs = [json.loads(root.joinpath(name).read_text(encoding="utf-8")) for name in ("company.json", "tax.json")]
    return {"version": "demo-2026-10-17-v1", "packs": packs, "rules": [r for p in packs for r in p["rules"]]}


def fields(expr: Any) -> set[str]:
    if not isinstance(expr, dict):
        return set()
    if "fact" in expr:
        return {expr["fact"]}
    return set().union(*(fields(x) for values in expr.values() for x in (values if isinstance(values, list) else [values])))


class PolicyEvaluator:
    def __init__(self, pack: dict | None = None, timeout_ms: int = 2000):
        self.pack = deepcopy(pack) if pack is not None else load_policy_pack()
        self.version = self.pack.get("version", "unknown")
        self.policy_hash = digest(self.pack)
        self.timeout_ms = timeout_ms
        self.symbols = {k: z3.Bool(k) if t == "bool" else z3.Int(k) if t == "int" else z3.String(k) for k, t in FACT_TYPES.items()}
        self.domains = [v >= 0 for k, v in self.symbols.items() if FACT_TYPES[k] == "int"]
        self.domains += [z3.Or(*[self.symbols[k] == value for value in t]) for k, t in FACT_TYPES.items() if isinstance(t, tuple)]
        self.compiled = []
        self.unsupported = []
        self._conflicts = None
        self._layer_cache = {}
        ids = set()
        for rule in self.pack.get("rules", []):
            if not isinstance(rule, dict):
                self.unsupported.append("Rule must be a JSON object")
                continue
            try:
                if rule["id"] in ids or rule["layer"] not in {"company", "tax"}:
                    raise ValueError("Duplicate rule ID or unsupported layer")
                ids.add(rule["id"])
                when, require = self.compile(rule["when"]), self.compile(rule["require"])
                if not z3.is_bool(when) or not z3.is_bool(require):
                    raise ValueError("Rule conditions must be boolean")
                self.compiled.append((rule, when, require))
            except (KeyError, TypeError, ValueError, z3.Z3Exception) as exc:
                self.unsupported.append(f"{rule.get('id', '?')}: {exc}")
        for layer in ("company", "tax"):
            if sum(r["layer"] == layer for r, _, _ in self.compiled) > 10:
                self.unsupported.append(f"{layer}: at most 10 rules per layer are supported by the exhaustive conflict check")

    def compile(self, expr):
        if type(expr) is bool:
            return z3.BoolVal(expr)
        if type(expr) is int:
            return z3.IntVal(expr)
        if type(expr) is str:
            return z3.StringVal(expr)
        if not isinstance(expr, dict) or len(expr) != 1:
            raise ValueError("Expected one typed policy operator")
        op, value = next(iter(expr.items()))
        if op == "fact":
            return self.symbols[value]
        if op == "not":
            return z3.Not(self.compile(value))
        args = [self.compile(x) for x in value]
        if op in {"and", "or"}:
            return z3.And(*args) if op == "and" else z3.Or(*args)
        if len(args) != 2:
            raise ValueError(f"{op} expects two operands")
        a, b = args
        operations = {"eq": lambda: a == b, "ne": lambda: a != b, "gt": lambda: a > b, "ge": lambda: a >= b, "lt": lambda: a < b, "le": lambda: a <= b}
        if op not in operations:
            raise ValueError(f"Unsupported operator: {op}")
        return operations[op]()

    def possible(self, expressions) -> bool:
        solver = z3.Solver()
        solver.set(timeout=self.timeout_ms)
        solver.add(*self.domains, *expressions)
        result = solver.check()
        if result == z3.unknown:
            raise RuntimeError(f"Solver could not decide: {solver.reason_unknown()}")
        return result == z3.sat

    def _constraints(self, facts):
        return [self.symbols[k] == self.compile(f.value) for k, f in facts.items() if f.value is not None]

    def _layer(self, layer, facts):
        members = [(r, w, q) for r, w, q in self.compiled if r["layer"] == layer]
        relevant = set().union(*(fields(r["when"]) | fields(r["require"]) for r, _, _ in members))
        key = (layer, tuple((k, facts[k].value if k in facts else None) for k in sorted(relevant)))
        if key in self._layer_cache:
            return self._layer_cache[key].model_copy(deep=True)
        constraints = self._constraints({k:v for k,v in facts.items() if k in relevant})
        out = LayerResult()
        if not members:
            out.verdict = "not_applicable"
            return out
        axioms = [z3.Implies(w, q) for _, w, q in members]
        any_trigger = z3.Or(*[w for _, w, _ in members])
        for r, w, q in members:
            can_trigger = self.possible(constraints + [w])
            can_fail = self.possible(constraints + [w, z3.Not(q)])
            can_pass = self.possible(constraints + [z3.Implies(w, q)])
            verdict = "not_applicable" if not can_trigger else "violation" if not can_pass else "undetermined" if can_fail else "compliant"
            definite_trigger = not self.possible(constraints + [z3.Not(w)])
            if layer == "tax" and can_trigger and not definite_trigger:
                # Correct coding alone does not establish eligibility for tax treatment.
                verdict = "undetermined"
            missing = sorted(k for k in fields(r["when"]) | fields(r["require"]) if k not in facts or facts[k].value is None)
            out.rules.append(RuleResult(rule_id=r["id"], layer=layer, verdict=verdict, missing_facts=missing if verdict == "undetermined" else []))
            if definite_trigger:
                out.applicable_rule_ids.append(r["id"])
            if verdict == "violation":
                out.violated_rule_ids.append(r["id"])
        if not self.possible(constraints + [any_trigger]):
            out.verdict = "not_applicable"
        elif not self.possible(constraints + axioms):
            out.verdict = "violation"
        elif self.possible(constraints + [z3.Not(z3.And(*axioms))]):
            out.verdict = "undetermined"
        elif layer == "tax" and any(r.verdict == "undetermined" for r in out.rules):
            out.verdict = "undetermined"
        else:
            out.verdict = "compliant"
        # Bound the process-local cache; entries depend on this immutable compiled policy.
        if len(self._layer_cache) >= 4096:
            self._layer_cache.clear()
        self._layer_cache[key] = out.model_copy(deep=True)
        return out

    def conflicts(self):
        if self._conflicts is not None:
            return self._conflicts
        conflicts = []
        minimal = []
        for layer in ("company", "tax"):
            members = [entry for entry in self.compiled if entry[0]["layer"] == layer]
            for size in range(2, len(members)+1):
                for group in itertools.combinations(members, size):
                    ids = {r["id"] for r, _, _ in group}
                    if any(existing <= ids for existing in minimal):
                        continue
                    overlap = [w for _, w, _ in group]
                    requirements = [q for _, _, q in group]
                    # Trigger overlap must be feasible. Individually valid obligations
                    # may conflict only in combination (including three-way conflicts).
                    if (self.possible(overlap) and not self.possible(overlap+requirements)
                            and all(self.possible(overlap+[q]) for q in requirements)):
                        minimal.append(ids)
                        conflicts.append("Conflicting rules: " + " / ".join(sorted(ids)))
        self._conflicts = conflicts
        return conflicts

    def evaluate(self, case: PurchaseCase, *, suggestions=True) -> EvaluationResult:
        facts = case.resolved_facts()
        result = EvaluationResult(case_id=case.case_id, company_id=case.company_id, policy_version=self.version, policy_hash=self.policy_hash, facts_hash=digest(facts_to_json(facts)), facts=facts)
        if case.policy_version != self.version:
            result.status = "unsupported"
            result.diagnostics = [f"Requested policy {case.policy_version}, loaded {self.version}"]
            return result
        if self.unsupported:
            result.status, result.diagnostics = "unsupported", list(self.unsupported)
            return result
        try:
            conflict = self.conflicts()
            if conflict:
                result.status, result.diagnostics = "conflicting_policy", conflict
                return result
            result.company = self._layer("company", facts)
            result.tax = self._layer("tax", facts)
            if suggestions:
                for layer_result, layer in [(result.company, "company"), (result.tax, "tax")]:
                    unknown = sorted({key for r in layer_result.rules for key in r.missing_facts})
                    for key in unknown:
                        spec = FACT_TYPES[key]
                        if spec == "int":
                            continue
                        candidates = [False, True] if spec == "bool" else list(spec)
                        outcomes = {}
                        for value in candidates:
                            alternative = {**facts, key: Fact(value=value, source="hypothetical_question")}
                            branch = self._layer(layer, alternative)
                            outcomes[str(value)] = {"verdict": branch.verdict, "violated_rule_ids": branch.violated_rule_ids}
                        deciding_alone = len({json.dumps(v, sort_keys=True) for v in outcomes.values()}) > 1
                        # Several facts may be jointly necessary even when no single answer
                        # settles the aggregate verdict yet (e.g. meal qualifications).
                        result.questions.append({"fact": key, "layer": layer, "outcomes": outcomes,
                            "deciding_alone": deciding_alone,
                            "rule_ids": [r.rule_id for r in layer_result.rules if key in r.missing_facts],
                            "request": f"Confirm {key.replace('_', ' ')} with evidence."})
                    for rule_result in layer_result.rules:
                        if rule_result.verdict not in {"violation", "undetermined"}:
                            continue
                        rule = next(r for r, _, _ in self.compiled if r["id"] == rule_result.rule_id)
                        if rule.get("fix"):
                            result.proposed_fixes.append({"rule_id": rule["id"], "layer": layer, **rule["fix"], "requires_recheck": True})
        except (RuntimeError, z3.Z3Exception) as exc:
            result.status, result.diagnostics = "error", [str(exc)]
        return result


def facts_to_json(facts):
    return {k: v.model_dump(mode="json") for k, v in facts.items()}
