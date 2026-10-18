"""Build the held-out set, run the four systems, write predictions.jsonl and results.json.

    .venv/bin/python -m eval.run              # everything (~270 Claude CLI calls, ~210 Jev calls)
    .venv/bin/python -m eval.run --skip-llm   # only Keyword rules and Jev + Z3; LLM rows are kept from the last run
"""
import argparse
import json
import os
import random
import re
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from api.try_text import load_env  # noqa: E402

load_env(ROOT / ".env")

from api import bench_jev, cases, jev_live, models  # noqa: E402
from api.policy_nl import _claude  # noqa: E402
from engine.keyword_baseline import extract_stub, keyword_verdict  # noqa: E402
from engine.rules import facts_from_probs  # noqa: E402
from eval import gold  # noqa: E402

EVAL = Path(__file__).resolve().parent
HELDOUT, PREDICTIONS, RESULTS = EVAL / "heldout.jsonl", EVAL / "predictions.jsonl", EVAL / "results.json"
JEV_USD_PER_M_INPUT = 0.042  # Typesafe list price per third-party trackers (output tokens free); see README
LLM_RERUN_N = 30
QB_CATEGORY = {"meal": "Meals", "rideshare": "Travel", "airfare": "Travel", "hotel": "Travel",
               "software": "Office", "equipment": "Office", "entertainment": "Entertainment", "other": "Other"}
SEMANTIC = ("expense_kind", "client_present", "at_company_event")


# ---- held-out set ----
def build_heldout() -> list[dict]:
    """Every human-labeled text in api/bench_jev.py (no None label) x 2-3 structured contexts."""
    out = []
    texts = [c for c in bench_jev.CASES if None not in c[1:]]
    for i, (text, kind, client, event) in enumerate(texts):
        amount = cases.parse_amount(text)
        base = dict(role="employee", tenure_days=400, hour=12, pre_approved=False, receipt_attached=True)
        if kind == "meal":  # interns/contractors, late or early meals
            stress = dict(role=("intern", "contractor")[i % 2], tenure_days=60,  # contractors unapproved: 6.1/6.2 fire too
                          hour=5 if "breakfast" in text.lower() else 23, pre_approved=i % 2 == 0, receipt_attached=False)
        elif kind in ("rideshare", "airfare"):  # interns and transport
            stress = dict(role="intern", tenure_days=60, hour=12, pre_approved=True, receipt_attached=False)
        elif kind in ("hotel", "equipment", "entertainment"):  # first-90-days rules
            stress = dict(role="employee", tenure_days=20, hour=12, pre_approved=False, receipt_attached=False)
        else:  # software / other: a contractor, no receipt
            stress = dict(role="contractor", tenure_days=200, hour=12, pre_approved=True, receipt_attached=False)
        ctxs = [("base", base), ("stress", stress)]
        if i % 2 == 0 or amount > 500:  # pre-approved, receipt unknown: the compliant / undetermined side
            ctxs.append(("approved", dict(role="employee", tenure_days=400, hour=12, pre_approved=True, receipt_attached=None)))
        for tag, ctx in ctxs:
            context = {**ctx, "amount": amount, "days_since_purchase": 0}
            labels = {"expense_kind": kind, "client_present": client, "at_company_event": event}
            v, rules = gold.verdict(cases.PACK_RULES, {**known(context), **labels, "coded_account": gold.coded_account(kind, event)})
            out.append({"case_id": f"h{len(out) + 1:03d}", "context_tag": tag, "text": text, "context": context,
                        "labels": labels, "gold_verdict": v, "gold_rules": rules})
    return out


def known(context: dict) -> dict:
    return {k: v for k, v in context.items() if v is not None}


def gold_vs_z3(heldout: list[dict]) -> tuple[float, list[dict]]:
    """Feed the gold facts to the real Z3 policy; the two must agree or the README has to explain why."""
    bad = []
    for c in heldout:
        d = cases.POLICY.decide({**known(c["context"]), **c["labels"]}, {})
        z = (d.verdict.status, sorted(v.rule for v in d.verdict.violations))
        if z != (c["gold_verdict"], sorted(c["gold_rules"])):
            bad.append({"case_id": c["case_id"], "gold": [c["gold_verdict"], c["gold_rules"]], "z3": list(z)})
    return 1 - len(bad) / len(heldout), bad


# ---- systems: each returns a prediction dict ----
def z3_decide(c: dict, probs: dict) -> tuple[dict, float]:
    t0 = time.perf_counter()
    d = cases.POLICY.decide({**facts_from_probs(probs), **known(c["context"])}, probs)
    return {"verdict": d.verdict.status, "rules": sorted(v.rule for v in d.verdict.violations),
            "questions": list(d.questions)}, (time.perf_counter() - t0) * 1000


def sys_keyword(c: dict) -> dict:
    ctx = c["context"]
    day = cases.now_la().date().isoformat()  # days_since_purchase 0, like the Z3 systems
    txn = {"memo": c["text"], "amount": ctx["amount"], "timestamp": f"{day}T{ctx['hour']:02d}:00:00",
           "receipt_attached": ctx["receipt_attached"], "receipt_date": None,
           "qb_category": QB_CATEGORY[c["labels"]["expense_kind"]]}  # the bookkeeper's category, see README
    t0 = time.perf_counter()
    extract_stub(c["text"])  # the baseline's own reading step, timed with it
    r = keyword_verdict(txn, pre_approved=ctx["pre_approved"])
    return {"verdict": r["verdict"], "rules": sorted(r["rules"]), "latency_ms": (time.perf_counter() - t0) * 1000, "cost_usd": 0.0}


def sys_jev(c: dict) -> dict:
    for attempt in (1, 2):
        try:
            probs, meta = jev_live.extract_with_meta(c["text"])
            break
        except Exception as e:  # noqa: BLE001
            if attempt == 2:
                return {"verdict": None, "rules": [], "latency_ms": None, "cost_usd": None, "error": f"{type(e).__name__}: {e}"}
    pred, dt = z3_decide(c, probs)
    tokens = (meta.get("usage") or {}).get("input_tokens") or 0
    return {**pred, "latency_ms": meta["latency_ms"] + dt, "cost_usd": tokens * JEV_USD_PER_M_INPUT / 1e6,
            "raw": {"probs": probs, "usage": meta.get("usage"), "model": meta.get("model")}}


def claude_json(prompt: str, system: str) -> tuple[dict | None, dict]:
    """One `claude -p` call with nothing loaded but the prompt: no tools, settings, CLAUDE.md or MCP servers."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}
    cmd = [_claude(), "-p", prompt, "--output-format", "json", "--model", "sonnet", "--tools", "", "--safe-mode",
           "--strict-mcp-config", "--setting-sources", "", "--system-prompt", system]
    t0 = time.perf_counter()
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=240, env=env, cwd=EVAL)
        d = json.loads(out.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        return None, {"error": f"cli: {type(e).__name__}", "wall_ms": (time.perf_counter() - t0) * 1000, "cost_usd": None, "duration_ms": None}
    meta = {"duration_ms": d.get("duration_ms"), "duration_api_ms": d.get("duration_api_ms"), "cost_usd": d.get("total_cost_usd"),
            "wall_ms": (time.perf_counter() - t0) * 1000, "input_tokens": (d.get("usage") or {}).get("input_tokens"),
            "text": (d.get("result") or "")[:500], "error": d.get("is_error") and "cli: is_error"}
    m = re.search(r"\{.*\}", d.get("result") or "", re.S)
    try:
        return (json.loads(m.group(0)) if m else None), meta
    except json.JSONDecodeError:
        return None, meta


def _context_lines(c: dict) -> str:
    ctx = c["context"]
    return "\n".join(f"- {k}: {'unknown' if v is None else v}" for k, v in ctx.items())


def rules_text() -> str:
    return "\n".join(f"{r['id']}: {r['text']}" for r in cases.PACK_RULES)


JUDGE_SYSTEM = "You are an expense-policy compliance checker. Answer with ONE JSON object and nothing else."


def judge_prompt(c: dict) -> str:
    return f"""Decide whether this purchase complies with the policy below.

Policy rules (id: text). Each rule applies only when its condition holds.
{rules_text()}

Facts from records (hour is 0-23 local; tenure_days is days since the employee's start date; pre_approved is whether
a manager approved it in advance; receipt_attached "unknown" means nobody has checked yet):
{_context_lines(c)}

Purchase request text (read the kind of expense, whether a client/customer/prospect/investor was present, and whether
it was at a company-organized event such as an offsite, all-hands, kickoff, team outing or holiday party):
"{c['text']}"

The "IRS-" rules decide how the expense is coded for tax; the bookkeeper posts coded_account to satisfy them, so they
are not violated by the purchase itself. Cite only the ids of rules that are violated.

Answer with exactly: {{"verdict": "compliant" | "violation" | "undetermined", "rules": [<ids of violated rules>]}}
"violation" if at least one rule is definitely violated (list every violated rule id).
"undetermined" if no rule is definitely violated but some rule's outcome depends on a fact that is unknown.
"compliant" otherwise, with "rules": []."""


FACTS_SYSTEM = "You read a short purchase request and answer three typed questions. Answer with ONE JSON object and nothing else."


def facts_prompt(c: dict) -> str:
    q = jev_live.QUESTIONS
    kinds = "\n".join(f"  - {k}: {v}" for k, v in q["expense_kind"]["criteria"].items())
    return f"""Purchase request: "{c['text']}"

1. expense_kind: pick exactly one of
{kinds}
2. client_present: {q['client_present']['instructions']}
3. at_company_event: {q['at_company_event']['instructions']}

Answer with exactly: {{"expense_kind": {{"value": "<one of the kinds>", "p": <your confidence 0-1>}},
"client_present": {{"p": <probability the answer is yes, 0-1>}}, "at_company_event": {{"p": <probability yes, 0-1>}}}}"""


VERDICTS = {"compliant", "violation", "undetermined"}


def sys_llm_judge(c: dict) -> dict:
    ans, meta = claude_json(judge_prompt(c), JUDGE_SYSTEM)
    verdict, rules, err = None, [], meta.get("error")
    if isinstance(ans, dict) and ans.get("verdict") in VERDICTS and isinstance(ans.get("rules"), list):
        verdict, rules = ans["verdict"], sorted(str(r) for r in ans["rules"])
        if verdict != "violation":
            rules = []  # a non-violation verdict has an empty set by definition
    else:
        err = err or f"malformed: {meta.get('text')!r}"
    return {"verdict": verdict, "rules": rules, "latency_ms": meta.get("duration_ms"), "cost_usd": meta.get("cost_usd"),
            "error": err or None, "raw": {k: meta.get(k) for k in ("duration_api_ms", "wall_ms", "input_tokens", "text")}}


def sys_llm_facts(c: dict) -> dict:
    ans, meta = claude_json(facts_prompt(c), FACTS_SYSTEM)
    probs = {}
    if isinstance(ans, dict):
        for k in SEMANTIC:
            if isinstance(ans.get(k), dict):
                probs[k] = ans[k]
    if not probs:
        return {"verdict": None, "rules": [], "latency_ms": meta.get("duration_ms"), "cost_usd": meta.get("cost_usd"),
                "error": meta.get("error") or f"malformed: {meta.get('text')!r}", "raw": meta}
    pred, dt = z3_decide(c, probs)
    return {**pred, "latency_ms": (meta.get("duration_ms") or 0) + dt, "cost_usd": meta.get("cost_usd"), "error": meta.get("error") or None,
            "raw": {"probs": probs, **{k: meta.get(k) for k in ("duration_api_ms", "wall_ms", "input_tokens")}}}


SYSTEMS = {"Keyword rules": (sys_keyword, 1), "LLM judge": (sys_llm_judge, 6), "LLM facts + Z3": (sys_llm_facts, 6), "Jev + Z3": (sys_jev, 1)}
LLM = ("LLM judge", "LLM facts + Z3")


# ---- metrics ----
def metrics(name: str, rows: list[dict], heldout: list[dict]) -> dict:
    g = {c["case_id"]: (c["gold_verdict"], set(c["gold_rules"])) for c in heldout}
    r1 = {r["case_id"]: r for r in rows if r["run"] == 1}
    r2 = {r["case_id"]: r for r in rows if r["run"] == 2}
    tp = fp = fn = 0
    for cid, r in r1.items():
        p, gs = set(r["rules"]), g[cid][1]
        tp, fp, fn = tp + len(p & gs), fp + len(p - gs), fn + len(gs - p)
    same = [(r1[cid]["verdict"], r1[cid]["rules"]) == (r["verdict"], r["rules"]) for cid, r in r2.items()]
    lat = [r["latency_ms"] for r in r1.values() if r["latency_ms"] is not None]
    cost = [r["cost_usd"] or 0.0 for r in r1.values()]
    return {"name": name,
            "accuracy": round(sum(r["verdict"] == g[cid][0] for cid, r in r1.items()) / len(r1), 4),
            "citation_f1": round(2 * tp / (2 * tp + fp + fn), 4) if (2 * tp + fp + fn) else 1.0,
            "rerun_agreement": round(sum(same) / len(same), 4) if same else 0.0,
            "median_latency_ms": round(statistics.median(lat), 2) if lat else 0.0,
            "cost_per_1k_usd": round(statistics.mean(cost) * 1000, 4) if cost else 0.0,
            "questions_per_txn": round(statistics.mean(len(r.get("questions") or []) for r in r1.values()), 4)}


def run_system(name: str, heldout: list[dict], rerun_ids: set[str]) -> list[dict]:
    fn, workers = SYSTEMS[name]
    jobs = [(c, run) for run in (1, 2) for c in heldout if run == 1 or c["case_id"] in rerun_ids]
    t0 = time.perf_counter()
    with ThreadPoolExecutor(workers) as ex:
        preds = list(ex.map(lambda j: fn(j[0]), jobs))
    rows = [{"system": name, "run": run, "case_id": c["case_id"], **p} for (c, run), p in zip(jobs, preds)]
    errs = sum(1 for r in rows if r.get("error"))
    print(f"{name}: {len(rows)} predictions in {time.perf_counter() - t0:.0f}s, {errs} errors", flush=True)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-llm", action="store_true", help="rerun only Keyword rules and Jev + Z3; keep LLM rows from predictions.jsonl")
    a = ap.parse_args(argv)

    heldout = build_heldout()
    HELDOUT.write_text("".join(json.dumps(c) + "\n" for c in heldout))
    agreement, disagreements = gold_vs_z3(heldout)
    print(f"held-out: {len(heldout)} cases; gold vs Z3 agreement {agreement:.3f}; disagreements {disagreements}")

    ids = [c["case_id"] for c in heldout]
    llm_rerun = set(random.Random(0).sample(ids, LLM_RERUN_N))
    old = [json.loads(l) for l in PREDICTIONS.read_text().splitlines()] if PREDICTIONS.exists() else []
    rows = []
    for name in SYSTEMS:
        if a.skip_llm and name in LLM:
            rows += [r for r in old if r["system"] == name]
            continue
        rows += run_system(name, heldout, set(ids) if name not in LLM else llm_rerun)
    PREDICTIONS.write_text("".join(json.dumps(r) + "\n" for r in rows))

    llm_rows = [r for r in rows if r["system"] in LLM]
    out = {"as_of": cases.now_la().isoformat(timespec="seconds"), "n_heldout": len(heldout),
           "systems": [metrics(n, [r for r in rows if r["system"] == n], heldout) for n in SYSTEMS if any(r["system"] == n for r in rows)],
           "notes": {"policy_version": cases.POLICY.version, "gold_vs_z3_agreement": round(agreement, 4),
                     "gold_vs_z3_disagreements": disagreements, "llm_rerun_subset": LLM_RERUN_N,
                     "llm_cli_calls": len(llm_rows), "llm_total_cost_usd": round(sum(r["cost_usd"] or 0 for r in llm_rows), 4),
                     "jev_price_usd_per_m_input_tokens": JEV_USD_PER_M_INPUT, "jev_output_tokens_priced": 0,
                     "rerun": "Keyword rules and Jev + Z3: every case twice; LLM systems: a fixed random 30-case subset"}}
    RESULTS.write_text(json.dumps(out, indent=1) + "\n")
    models.EvalOut.model_validate_json(RESULTS.read_text())
    for s in out["systems"]:
        print(s)


if __name__ == "__main__":
    main()
