"""Try plaintext purchase requests against live Jev + the Z3 engine.

python -m api.try_text "Client dinner with Acme's CFO, about $48" [--employee e_newhire] [--amount 48]
    [--timestamp 2026-10-17T19:30:00-07:00] [--local] [--json] [--env PATH] | --demo
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from api import jev_live
from api.cases import parse_amount
from api.explain import explain, question
from engine.keyword_baseline import LA, extract_stub
from engine.rules import facts_from_probs, load_policy

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "engine"
ROLES = {"e_newhire": "employee", "e_intern": "intern", "e_contractor": "contractor", "e_manager": "employee"}
DEMO = [
    "Client dinner with Acme's CFO, about $48",
    ("Lyft to the team offsite, $30", "e_intern"),
    ("Lunch with the design team, $22", "e_contractor"),
    "Team dinner tonight",
    "Concert ticket for a prospect, $150",
    "Hotel night in Chicago, $350",
    "Dell monitor for my desk, $300",
    "Coffee with a coworker, $20",
    "Flight to New York for the sales kickoff, $480",
    "Annual Figma subscription, $144",
]


def load_env(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        k, sep, v = line.strip().partition("=")
        if sep and not k.startswith("#") and k.strip():
            os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


def run(P, text, employee, amount, timestamp, local):
    meta = {}
    if local:
        probs = extract_stub(text)
    else:
        probs, meta = jev_live.extract_with_meta(text)
    # ponytail: Task 8 replaces this block with api.cases.build_facts
    if amount is None:
        amount = parse_amount(text)
    now = datetime.now(LA)
    if timestamp:
        ts = datetime.fromisoformat(timestamp)
        ts = ts.replace(tzinfo=LA) if ts.tzinfo is None else ts.astimezone(LA)
        hour = ts.hour if len(timestamp) > 10 else None
    else:
        ts, hour = now, now.hour
    facts = {"role": ROLES[employee], "days_since_purchase": max(0, (now - ts).days), "pre_approved": False}
    if amount is not None:
        facts["amount"] = amount
    if hour is not None:
        facts["hour"] = hour
    sources = {k: "request" for k in facts}
    for k, v in facts_from_probs(probs).items():
        facts[k], sources[k] = v, "local stub" if local else "jev"
    d = P.decide(facts, probs)
    # the API's rule: undetermined with no yes/no question -> ask for the first missing amount/expense_kind
    qs = list(d.questions)
    if d.verdict.status == "undetermined" and not qs:
        qs = [f for f in ("expense_kind", "amount") if f not in d.facts][:1]
    return {
        "text": text, "employee": employee, "jev": meta, "probs": probs,
        "facts": {k: {"value": v, "source": sources.get(k, "derived")} for k, v in d.facts.items()},
        "verdict": d.verdict.status,
        "violations": [{"rule": v.rule, "text": P.by_id[v.rule].text, "because": v.because} for v in d.verdict.violations],
        "fix": None if d.fix is None else [{"fact": s.fact, "from": s.from_, "to": s.to} for s in d.fix],
        "questions": [question(f, (probs.get(f) or {}).get("p")) for f in qs],
        "explanation": explain(d, P.by_id, qs),
    }


def show(r):
    print(f"\n=== {r['text']}  [{r['employee']}]")
    if r["jev"]:
        print(f"jev: {r['jev']['model']}  {r['jev']['latency_ms']} ms  usage {r['jev']['usage']}")
    print("probs: " + json.dumps(r["probs"]))
    print("facts: " + ", ".join(f"{k}={v['value']} ({v['source']})" for k, v in r["facts"].items()))
    print(f"verdict: {r['verdict']}")
    for v in r["violations"]:
        print(f"  violation {v['rule']}: {v['text']} because {', '.join(v['because'])}")
    if r["fix"] is not None:
        print("fix: " + ("; ".join(f"{s['fact']}: {s['from']} -> {s['to']}" for s in r["fix"]) or "none needed"))
    else:
        print("fix: none within your control")
    for q in r["questions"]:
        print(f"  question: {q['text']} (p={q['p']}, options={q['options']})")
    print("explanation: " + r["explanation"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m api.try_text")
    ap.add_argument("text", nargs="?")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--employee", default="e_newhire", choices=sorted(ROLES))
    ap.add_argument("--amount", type=float)
    ap.add_argument("--timestamp")
    ap.add_argument("--local", action="store_true", help="keyword stub instead of live Jev")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--env", default=str(ROOT / ".env"))
    a = ap.parse_args(argv)
    if not a.demo and not a.text:
        ap.error("give a text or --demo")
    if a.timestamp:
        try:
            datetime.fromisoformat(a.timestamp)
        except ValueError:
            ap.error(f"--timestamp must be ISO 8601, e.g. 2026-10-17T19:30:00-07:00 (got {a.timestamp!r})")
    load_env(Path(a.env))
    P = load_policy(ENGINE / "demo_policy.json", ENGINE / "irs_pack.json")
    code = 0
    for text, emp in [(t, a.employee) if isinstance(t, str) else t for t in DEMO] if a.demo else [(a.text, a.employee)]:
        try:
            r = run(P, text, emp, a.amount, a.timestamp, a.local)
        except (jev_live.JevError, RuntimeError) as e:
            print(f"error: {text!r}: {e}", file=sys.stderr)
            code = 1
            if a.demo:
                continue
            return 1
        print(json.dumps(r, default=str)) if a.json else show(r)
    return code


if __name__ == "__main__":
    sys.exit(main())
