"""
Natural Language to Z3 Proof Compiler.
Translates human natural language policy statements into formal Z3 rule ASTs,
and uses Z3 SMT solving to formally prove the rule's validity, reachability, and safety.
"""

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import z3

from engine.rules import ENGINE_LOCK, Policy, Rule, _sat, compile_expr, load_policy
from engine.schema import FACTS

# Auto-load .env
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    with open(_env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v


def _heuristic_compile_to_ast(prompt: str) -> Dict[str, Any]:
    """Deterministic fallback AST compiler matching schema FACTS."""
    p_lower = prompt.lower()

    when_clauses = []
    require_expr: Any = "pre_approved"

    # 1. Role / Who
    if "intern" in p_lower:
        when_clauses.append({"eq": ["role", "intern"]})
    elif "contractor" in p_lower:
        when_clauses.append({"eq": ["role", "contractor"]})
    elif "engineer" in p_lower:
        when_clauses.append({"eq": ["role", "employee"]})

    # 2. Expense Kind
    kinds = []
    if any(k in p_lower for k in ["saas", "software", "cloud", "aws", "hosting"]):
        kinds.append("software")
    if any(k in p_lower for k in ["meal", "dinner", "lunch", "food", "restaurant"]):
        kinds.append("meal")
    if any(k in p_lower for k in ["uber", "lyft", "rideshare", "taxi", "transport"]):
        kinds.append("rideshare")
    if any(k in p_lower for k in ["flight", "airfare", "airline"]):
        kinds.append("airfare")
    if any(k in p_lower for k in ["hotel", "lodging", "airbnb"]):
        kinds.append("lodging")
    if any(k in p_lower for k in ["laptop", "monitor", "equipment", "hardware"]):
        kinds.append("equipment")

    if len(kinds) == 1:
        when_clauses.append({"eq": ["expense_kind", kinds[0]]})
    elif len(kinds) > 1:
        when_clauses.append({"in": ["expense_kind", kinds]})

    # 3. Threshold / Amount
    amt_match = re.search(r"\$([0-9,]+(?:\.[0-9]{2})?)", prompt)
    if amt_match:
        amt = float(amt_match.group(1).replace(",", ""))
        if any(w in p_lower for w in ["over", "above", "exceed", ">", "cap"]):
            when_clauses.append({"gt": ["amount", amt]})
        elif any(w in p_lower for w in ["under", "below", "<"]):
            when_clauses.append({"lt": ["amount", amt]})
        else:
            when_clauses.append({"gt": ["amount", amt]})

    # 4. Actions & Requirements
    if any(k in p_lower for k in ["receipt", "receipts"]):
        require_expr = "receipt_attached"
    elif any(k in p_lower for k in ["event", "company event", "offsite"]):
        require_expr = "at_company_event"
    elif any(k in p_lower for k in ["block", "never", "deny", "not reimbursed"]):
        require_expr = False
    else:
        require_expr = "pre_approved"

    # Default when condition if nothing caught
    if not when_clauses:
        when_clauses.append({"gt": ["amount", 100.0]})

    when_expr = when_clauses[0] if len(when_clauses) == 1 else {"and": when_clauses}

    rule_hash = hashlib.sha256(prompt.encode()).hexdigest()[:8]
    return {
        "id": f"rule_{rule_hash}",
        "layer": "company",
        "text": prompt,
        "when": when_expr,
        "require": require_expr,
    }


def compile_nl_to_ast(prompt: str) -> Dict[str, Any]:
    """Compiles natural language to rule AST using Gemini free tier or OpenRouter, with resilient fallback."""
    schema_description = {
        "allowed_facts": {
            "role": ["employee", "contractor", "intern"],
            "expense_kind": [
                "meal",
                "rideshare",
                "airfare",
                "hotel",
                "software",
                "equipment",
                "entertainment",
                "other",
            ],
            "amount": "number > 0",
            "hour": "0-23",
            "days_since_purchase": "int >= 0",
            "receipt_attached": "bool",
            "pre_approved": "bool",
            "client_present": "bool",
            "at_company_event": "bool",
        },
        "grammar": '{"id": string, "layer": "company", "text": string, "when": expression, "require": expression}',
        "operators": ["eq", "neq", "gt", "ge", "lt", "le", "in", "and", "or", "not"],
    }
    system_prompt = (
        "You are an SMT Rule Compiler. Translate the user's natural language expense policy into a JSON AST rule.\n"
        f"Schema: {json.dumps(schema_description)}\n"
        "Return ONLY a valid JSON object matching the grammar."
    )

    # 1. Try Gemini Free Tier via Google AI Studio
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key and gemini_key != "your-gemini-api-key-here":
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
            resp = httpx.post(
                url,
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [
                        {"parts": [{"text": f"{system_prompt}\n\nPolicy prompt: {prompt}"}]}
                    ],
                    "generationConfig": {
                        "response_mime_type": "application/json"
                    }
                },
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                parsed = json.loads(content)
                if "when" in parsed and "require" in parsed:
                    parsed.setdefault("layer", "company")
                    parsed.setdefault("text", prompt)
                    parsed.setdefault("id", f"rule_{hashlib.sha256(prompt.encode()).hexdigest()[:8]}")
                    return parsed
        except Exception:
            pass

    # 2. Try OpenRouter
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key:
        try:
            resp = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {openrouter_key}", "Content-Type": "application/json"},
                json={
                    "model": "nvidia/nemotron-3.5-lightning:free",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "response_format": {"type": "json_object"},
                },
                timeout=8.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                parsed = json.loads(content)
                if "when" in parsed and "require" in parsed:
                    parsed.setdefault("layer", "company")
                    parsed.setdefault("text", prompt)
                    parsed.setdefault("id", f"rule_{hashlib.sha256(prompt.encode()).hexdigest()[:8]}")
                    return parsed
        except Exception:
            pass

    return _heuristic_compile_to_ast(prompt)


def prove_rule_with_z3(rule_ast: Dict[str, Any], policy: Optional[Policy] = None) -> Dict[str, Any]:
    """Formally proves safety, reachability, and non-conflict of the rule using Z3 SMT solver."""
    d = Path(__file__).parent
    base_policy = policy or load_policy(d / "demo_policy.json", d / "irs_pack.json")

    with ENGINE_LOCK:
        try:
            # 1. Compile candidate rule into Z3 expression to test syntax & AST validity
            when_z3 = compile_expr(rule_ast["when"], base_policy.vars)
            req_z3 = compile_expr(rule_ast["require"], base_policy.vars)
            formula_z3 = z3.Implies(when_z3, req_z3)

            # 2. Test Reachability: Can the condition ever trigger?
            if not _sat(*base_policy.dom, when_z3):
                return {
                    "status": "dead_rule",
                    "proved_safe": False,
                    "explanation": "Z3 mathematical proof: The condition can never trigger under schema bounds (dead rule).",
                    "formula": str(formula_z3),
                    "rule": rule_ast,
                }

            # 3. Test Non-Tautology: Can it ever be violated?
            if not _sat(*base_policy.dom, when_z3, z3.Not(req_z3)):
                return {
                    "status": "tautology",
                    "proved_safe": True,
                    "explanation": "Z3 mathematical proof: The rule is always satisfied across all inputs (tautology).",
                    "formula": str(formula_z3),
                    "rule": rule_ast,
                }

            # 4. Joint Audit against the entire Policy Pack (Company + IRS)
            existing_raw_rules = [r.raw for r in base_policy.rules]
            combined_policy = Policy([*existing_raw_rules, rule_ast])
            audit_result = combined_policy.audit()

            # Check if this rule is dead or involved in any conflict
            new_id = rule_ast["id"]
            if new_id in audit_result.get("dead", []):
                return {
                    "status": "dead_rule",
                    "proved_safe": False,
                    "explanation": "Z3 mathematical proof: Shadowed or unsatisfiable in combination with existing rules.",
                    "formula": str(formula_z3),
                    "rule": rule_ast,
                }

            conflicts_with = [
                c for c in audit_result.get("conflicts", [])
                if c["a"] == new_id or c["b"] == new_id
            ]

            if conflicts_with:
                c0 = conflicts_with[0]
                other_id = c0["b"] if c0["a"] == new_id else c0["a"]
                return {
                    "status": "conflict",
                    "proved_safe": False,
                    "conflicts": [other_id],
                    "example": c0.get("example"),
                    "explanation": f"Z3 mathematical proof: Conflicts with Rule {other_id}. Counterexample: {c0.get('example')}",
                    "formula": str(formula_z3),
                    "rule": rule_ast,
                }

            # 5. Formally Proven Safe
            return {
                "status": "valid",
                "proved_safe": True,
                "reachable": True,
                "can_fire": True,
                "conflicts": [],
                "explanation": "Z3 mathematical proof: Invariant is satisfiable, reachable, and free of contradictions.",
                "formula": str(formula_z3),
                "rule": rule_ast,
            }

        except Exception as exc:
            return {
                "status": "error",
                "proved_safe": False,
                "explanation": f"Z3 translation error: {exc}",
                "formula": None,
                "rule": rule_ast,
            }


def natural_language_to_proof(prompt: str) -> Dict[str, Any]:
    """End-to-end pipeline: Natural language prompt -> AST -> Formal Z3 proof."""
    ast = compile_nl_to_ast(prompt)
    proof = prove_rule_with_z3(ast)
    return {
        "prompt": prompt,
        "ast": ast,
        "proof": proof,
    }
