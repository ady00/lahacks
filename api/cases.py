"""Real case lifecycle: /check, /answer, /approve, /authorize, and decide_transaction for the ledger and eval."""
import hashlib
import json
import logging
import os
import re
import secrets
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import HTTPException

import engine
from api import db
from api.explain import MERCHANT_CATEGORY, explain, question
from engine.keyword_baseline import CODED_FALLBACK, extract_stub, txn_row
from engine.rules import Policy, _p, facts_from_probs
from engine.schema import FACTS, validate_value

log = logging.getLogger(__name__)
LA = ZoneInfo("America/Los_Angeles")
_PACKS = Path(engine.__file__).parent
PACK_RULES = [r for p in ("demo_policy.json", "irs_pack.json") for r in json.loads((_PACKS / p).read_text())]
POLICY = Policy(PACK_RULES)


def reload_policy(custom: list[dict] = ()) -> Policy:
    """Swap the live policy: packs first, then the dashboard's rules. Every route reads `cases.POLICY` at call time."""
    global POLICY
    POLICY = Policy(PACK_RULES + list(custom))
    return POLICY


def now_la() -> datetime:
    return datetime.now(LA)


# ---- Person B's functions, with fallbacks so the API always starts ----
def _extractor():
    """(name, fn, source) of the extractor /check will use: Person B's Jev, live Jev, or the keyword stub."""
    try:
        from extract.jev import extract as jev
        return "extract.jev", jev, "jev"
    except ImportError:
        pass
    if os.environ.get("TYPESAFE_API_KEY"):
        try:
            from api.jev_live import extract as live
            return "live Jev (api.jev_live)", live, "jev"
        except ImportError:
            pass
    return "keyword stub", extract_stub, "text"


def _extract_with_source(text: str) -> tuple[dict[str, dict], str]:
    name, fn, source = _extractor()
    if source == "jev":
        try:
            return fn(text), source
        except Exception:
            log.warning("%s failed; falling back to the keyword stub", name, exc_info=True)
    return extract_stub(text), "text"  # keyword guesses are not model facts: label them "text"


def extract(text: str) -> dict[str, dict]:
    return _extract_with_source(text)[0]


_EXTRACT = extract  # tests patch `extract` with a fake that stands in for Jev


def _model_facts(text: str) -> tuple[dict[str, dict], str]:
    return _extract_with_source(text) if extract is _EXTRACT else (extract(text), "jev")


def coded_account_for(qb_category: str) -> str:
    try:
        from extract.mapping import coded_account_for as mapping
    except ImportError:
        return CODED_FALLBACK.get(qb_category, "other")
    return mapping(qb_category)


# ---- parsing ----
_NUM = r"(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?\s*(k\b)?"
_AMOUNT = re.compile(rf"\$\s*{_NUM}|\b{_NUM}\s*(?:dollars|bucks|usd)\b", re.I)  # "$48", "$1.2k", "48 bucks", "1,200 USD"


def parse_amount(text: str) -> float | None:
    m = _AMOUNT.search(text or "")
    if not m:
        return None
    whole, cents, k = m.groups()[:3] if m.group(1) else m.groups()[3:]
    x = float(whole.replace(",", "") + "." + (cents or "0")) * (1000 if k else 1)
    return x or None


def parse_ts(s: str | None) -> tuple[datetime, bool]:
    """ISO 8601 -> (Los Angeles datetime, has_time). Naive is LA; None is now. Raises ValueError."""
    if s is None:
        return now_la(), True
    dt = datetime.fromisoformat(s.strip())
    dt = dt.replace(tzinfo=LA) if dt.tzinfo is None else dt.astimezone(LA)
    return dt, len(s.strip()) > 10


def _valid(name, value):
    try:
        return validate_value(name, value)
    except (KeyError, ValueError, TypeError):
        return None


# ---- facts -> case ----
def standing_facts(employee: dict | None, on: date | None = None) -> dict:
    """The facts an employee record alone decides: role, and tenure_days as of `on` (default today)."""
    out = {}
    if (role := _valid("role", (employee or {}).get("role"))) is not None:
        out["role"] = role
    try:
        start = date.fromisoformat((employee or {}).get("start_date") or "")
        out["tenure_days"] = max(0, ((on or now_la().date()) - start).days)
    except ValueError:
        pass
    return out


def build_facts(text, employee, amount, ts, has_time, answers, approved, probs=None, model_source="jev"):
    """-> (facts, probs, sources). `probs` given = re-proving a stored case without calling the model again."""
    probs = extract(text) if probs is None else probs
    facts, sources = {}, {}

    def put(name, value, source):
        facts[name], sources[name] = value, source

    for name, value in standing_facts(employee, ts.date()).items():
        put(name, value, "employee")
    for name, value in facts_from_probs(probs).items():
        put(name, value, model_source)
    if amount is not None:
        put("amount", amount, "user")
    elif (a := parse_amount(text)) is not None:
        put("amount", a, "text")
    if has_time:
        put("hour", ts.hour, "derived")
    put("days_since_purchase", max(0, (now_la() - ts).days), "derived")
    put("pre_approved", bool(approved), "approvals")
    for name, value in answers.items():
        put(name, value, "answer")
    return facts, probs, sources


def to_case(case_id, created_at, employee_id, text, decision, sources, probs, approval, authorization) -> dict:
    v = decision.verdict
    facts = {n: {"value": val, "source": sources.get(n, "rules"),
                 "p": _p(probs.get(n)) if sources.get(n) in ("jev", "text") else None}
             for n, val in decision.facts.items()}
    questions = [question(f, _p(probs.get(f))) for f in decision.questions]
    unknown = []
    if v.status == "undetermined" and not questions:
        unknown = [f for f in ("expense_kind", "amount") if f not in decision.facts][:1]
        questions += [question(f, None) for f in unknown]
    fix = None if decision.fix is None else [{"fact": s.fact, "from": s.from_, "to": s.to} for s in decision.fix]
    return {
        "case_id": case_id, "created_at": created_at, "employee_id": employee_id, "text": text,
        "policy_version": POLICY.version, "verdict": v.status, "facts": facts,
        "violations": [{"rule": x.rule, "layer": POLICY.by_id[x.rule].layer, "text": POLICY.by_id[x.rule].text,
                        "because": x.because} for x in v.violations],
        "applied": list(v.applied), "fix": fix, "questions": questions,
        "explanation": explain(decision, POLICY.by_id, unknown),
        "awaiting_approval": v.status == "violation" and any(s.fact == "pre_approved" for s in decision.fix or [])
                             and approval is None,
        "approval": approval, "authorization": authorization,
    }


def proof_hash(fact_values: dict, policy_version: str, verdict: str) -> str:
    blob = json.dumps({"facts": fact_values, "policy_version": policy_version, "verdict": verdict}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


# ---- case lifecycle ----
def _approval(conn, case_id):
    a = db.case_approval(conn, case_id)
    return {"approver": a["approver"], "approved": bool(a["approved"]), "at": a["at"]} if a else None


def _prove(conn, case_id, created_at, employee_id, text, amount, timestamp, probs, source, authorization) -> dict:
    """Run the full proof from stored inputs and save it. The extra keys (timestamp, _inputs) stay in the DB;
    the Case response model drops them."""
    ts, has_time = parse_ts(timestamp)
    answers = db.get_answers(conn, case_id)
    approval = _approval(conn, case_id)
    facts, probs, sources = build_facts(text, db.employee(conn, employee_id), amount, ts, has_time, answers,
                                        approval and approval["approved"], probs, source)
    case = to_case(case_id, created_at, employee_id, text, POLICY.decide(facts, probs), sources, probs,
                   approval, authorization)
    case["timestamp"], case["_inputs"] = timestamp, {"amount": amount, "probs": probs, "source": source}
    db.put_case(conn, case, answers)
    return case


def new_case(conn, req) -> dict:
    if db.employee(conn, req.employee_id) is None:
        raise HTTPException(404, "unknown employee")
    created_at = now_la().isoformat()
    timestamp = req.timestamp or created_at
    try:
        parse_ts(timestamp)
        amount = None if req.amount is None else validate_value("amount", req.amount)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return _prove(conn, "c_" + secrets.token_hex(4), created_at, req.employee_id, req.text, amount, timestamp,
                  *_model_facts(req.text), None)


def _get(conn, case_id) -> dict:
    case = db.get_case(conn, case_id)
    if case is None:
        raise HTTPException(404, "unknown case")
    return case


def rerun(conn, case_id) -> dict:
    c = _get(conn, case_id)
    return _prove(conn, case_id, c["created_at"], c["employee_id"], c["text"], c["_inputs"]["amount"],
                  c["timestamp"], c["_inputs"]["probs"],
                  c["_inputs"].get("source", "jev"), c["authorization"])


def answer(conn, case_id, fact, value) -> dict:
    case = _get(conn, case_id)
    if fact == "pre_approved":
        raise HTTPException(422, "pre_approved is set only by /approve")
    try:
        value = validate_value(fact, value)
    except KeyError:
        raise HTTPException(422, f"unknown fact {fact}")
    except ValueError as e:
        raise HTTPException(422, str(e))
    answers = db.get_answers(conn, case_id)
    answers[fact] = value
    db.put_case(conn, case, answers)
    return rerun(conn, case_id)


def approve(conn, case_id, approver, approved) -> dict:
    _get(conn, case_id)
    # txn_id = case_id too, so the ledger audit of this case's row sees the pre-approval
    db.add_approval(conn, case_id, case_id, approver, approved, now_la().isoformat())
    return rerun(conn, case_id)


def authorize(conn, case_id) -> dict:
    c = _get(conn, case_id)
    if c["authorization"]:
        return c["authorization"]
    c = rerun(conn, case_id)  # issue against a fresh proof, so proof_hash is the proof the card rests on
    if c["verdict"] != "compliant":
        raise HTTPException(409, "not compliant")
    facts = c["facts"]
    if "amount" not in facts:
        raise HTTPException(409, "amount unknown")
    kind = facts.get("expense_kind", {}).get("value", "other")  # ponytail: compliant with kind unknown -> "other" MCC
    values = {n: f["value"] for n, f in facts.items()}
    auth = {"auth_id": "auth_" + secrets.token_hex(4), "amount_limit": values["amount"],
            "merchant_category": MERCHANT_CATEGORY[kind], "expires_at": (now_la() + timedelta(hours=24)).isoformat(),
            "proof_hash": proof_hash(values, c["policy_version"], c["verdict"])}
    c["authorization"] = auth
    db.put_case(conn, c, db.get_answers(conn, case_id))
    coded = values.get("coded_account", "other")
    db.upsert_transactions(conn, [{
        "txn_id": case_id, "company": "demo", "employee_id": c["employee_id"], "vendor": "", "memo": c["text"],
        "amount": values["amount"], "timestamp": c["timestamp"],
        "qb_category": {v: k for k, v in CODED_FALLBACK.items()}.get(coded, "Other"), "coded_account": coded,
        "receipt_attached": values.get("receipt_attached"), "receipt_date": None, "source": "case",
        "extraction_json": json.dumps(c["_inputs"]["probs"], sort_keys=True)}])
    return auth


# ---- ledger / evaluation ----
def decide_transaction(txn: dict, extraction: dict | None, pre_approved: bool, employee: dict | None) -> dict:
    """One ledger row (raw CSV strings or a DB row) -> case dict. The ledger audit and eval/run.py both call this."""
    t = txn_row(txn)
    probs = extraction or {}
    facts, sources = {}, {}

    def put(name, value, source):
        if (value := _valid(name, value)) is not None:
            facts[name], sources[name] = value, source

    try:
        ts, has_time = parse_ts(t.get("timestamp")) if t.get("timestamp") else (None, False)
    except ValueError:
        ts, has_time = None, False
    for name, value in standing_facts(employee, ts.date() if ts else None).items():
        put(name, value, "employee")
    for name, value in facts_from_probs(probs).items():
        put(name, value, "jev")
    put("amount", t["amount"], "ledger")  # <= 0 or missing: unknown, never an all-rules-violated proof
    if ts is not None:
        if has_time:
            put("hour", ts.hour, "derived")
        end = now_la().date()
        if t["receipt_attached"] and t["receipt_date"]:
            try:
                end = date.fromisoformat(t["receipt_date"][:10])
            except ValueError:
                pass
        days = (end - ts.date()).days
        put("days_since_purchase", max(0, days), "derived")
    # a row this API wrote (source "case") carries its exact account; CSV rows map from the QuickBooks category
    put("coded_account", t.get("coded_account") or coded_account_for(t["qb_category"] or ""), "ledger")
    put("receipt_attached", t["receipt_attached"], "ledger")
    put("pre_approved", bool(pre_approved), "approvals")
    decision = POLICY.decide(facts, probs)
    return to_case(t.get("txn_id") or "", t.get("timestamp") or "", t["employee_id"] or "", t.get("memo") or "",
                   decision, sources, probs, None, None)
