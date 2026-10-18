"""Offline fallback extractor and the no-Z3 keyword baseline used in the evaluation."""
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

LA = ZoneInfo("America/Los_Angeles")

CODED_FALLBACK = {"Meals": "meals_50", "Travel": "travel", "Office": "office", "Entertainment": "entertainment_0"}

_KINDS = [  # first match wins, order is the contract
    ("meal", r"dinner|lunch|breakfast|meal|restaurant|coffee|drinks|catering|pizza|snacks"),
    ("rideshare", r"uber|lyft|taxi|cab|waymo|ride"),
    ("airfare", r"flight|airfare|airline|plane"),
    ("hotel", r"hotel|lodging|airbnb"),
    ("software", r"subscription|saas|license|software|seat|plan"),
    ("equipment", r"laptop|monitor|keyboard|webcam|charger|desk|equipment"),
    ("entertainment", r"tickets|concert|game|show|golf|outing"),
]


def extract_stub(text: str) -> dict[str, dict]:
    text = (text or "").lower()
    kind = next((k for k, rx in _KINDS if re.search(rx, text)), None)
    return {
        "expense_kind": {"value": kind or "other", "p": 0.9 if kind else 0.5},
        "client_present": {"p": 0.9 if re.search(r"client|customer|cfo|ceo|prospect|investor", text) else 0.5},
        "at_company_event": {"p": 0.9 if re.search(r"offsite|all-hands|company event|team event|team outing|kickoff|holiday party", text) else 0.1},
    }


def txn_row(txn: dict) -> dict:
    """Normalize a raw all-strings CSV row or a typed DB row to one shape (returns a new dict)."""
    t = dict(txn)
    amount = t.get("amount")
    t["amount"] = None if amount in (None, "") else float(amount)
    r = t.get("receipt_attached")
    r = None if r is None else str(r).strip().lower()
    t["receipt_attached"] = True if r in ("1", "true") else False if r in ("0", "false") else None
    for k in ("receipt_date", "employee_id", "qb_category"):
        t[k] = t.get(k) or None
    return t


def _parse(ts: str | None) -> tuple[date | None, int | None]:
    """(local date, hour); hour is None for a date-only string. Naive timestamps are Los Angeles."""
    if not ts:
        return None, None
    dt = datetime.fromisoformat(ts)
    dt = dt.replace(tzinfo=LA) if dt.tzinfo is None else dt.astimezone(LA)
    return dt.date(), (dt.hour if len(ts) > 10 else None)


def keyword_verdict(txn: dict, pre_approved: bool = False) -> dict:
    """Keyword rules with every Task 10 threshold as a literal predicate; never says undetermined.

    Each predicate is True when the rule is violated. Inputs the baseline does not know
    (missing amount, date-only hour) make the rule not fire.
    """
    t = txn_row(txn)
    receipt = t["receipt_attached"] is True
    bought, hour = _parse(t.get("timestamp"))
    end = date.fromisoformat(t["receipt_date"][:10]) if receipt and t["receipt_date"] else datetime.now(LA).date()
    days = (end - bought).days if bought else 0
    amount = t["amount"] or 0.0
    coded = CODED_FALLBACK.get(t["qb_category"], "other")
    ex = extract_stub(t.get("memo") or "")
    kind = ex["expense_kind"]["value"]
    client = ex["client_present"]["p"] >= 0.85
    event = ex["at_company_event"]["p"] >= 0.85
    pre = pre_approved
    # role is not in a txn row and the baseline has no employee lookup, so role is "employee":
    # the contractor/intern rules 5.1-5.3 can never fire here.
    rules = [
        ("3.4", amount > 35 and not pre),
        ("3.5", amount > 500 and not receipt),
        ("4.1", amount > 25 and days > 14 and not receipt),
        ("6.1", kind == "meal" and hour is not None and hour >= 22 and not pre),
        ("6.2", kind == "meal" and hour is not None and hour < 6 and not pre),
        ("6.3", kind == "entertainment" and not pre),
        ("6.4", kind == "entertainment" and amount > 100),
        ("6.5", kind == "meal" and client and amount > 150 and not pre),
        ("7.1", kind == "airfare" and not pre),
        ("7.2", kind == "hotel" and amount > 300 and not pre),
        ("8.1", kind == "software" and not pre),
        ("8.2", kind == "equipment" and amount > 250 and not (pre and receipt)),
        ("9.1", kind == "rideshare" and amount > 75 and not pre),
        ("IRS-meal", kind == "meal" and not event and coded != "meals_50"),
        ("IRS-meal-event", kind == "meal" and event and coded != "meals_100"),
        ("IRS-ent", kind == "entertainment" and coded != "entertainment_0"),
        ("IRS-travel", kind in ("rideshare", "airfare", "hotel") and coded != "travel"),
        ("IRS-office", kind in ("software", "equipment") and coded != "office"),
        ("IRS-other", kind == "other" and coded != "other"),
        ("IRS-receipt-60", days > 60 and not receipt),
        ("IRS-receipt-75", amount >= 75 and days > 0 and not receipt),
    ]
    hit = [rid for rid, violated in rules if violated]
    return {"verdict": "violation" if hit else "compliant", "rules": hit}
