"""Offline fallback extractor and the no-Z3 keyword baseline used in the evaluation."""
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

LA = ZoneInfo("America/Los_Angeles")

CODED_FALLBACK = {"Meals": "meals_50", "Travel": "travel", "Office": "office", "Entertainment": "entertainment_0"}

_KINDS = [  # first match wins, order is the contract
    ("business_cards", r"business cards?|\bmoo\b"),
    ("dry_cleaning", r"dry ?clean|laundry"),
    ("gift", r"gift|flowers"),
    ("entertainment", r"tickets?|concert|\bgame\b|golf|theat(er|re)|\bshow\b|bowling|karaoke|\bclub\b|box seats|suite at"),
    ("visa", r"\bvisa\b|permit|covid test|pcr test"),
    ("mileage", r"mileage|miles driven|drove \d+ ?mi"),
    ("fuel", r"\bgas\b|fuel|petrol|ev charg|charging station|supercharg"),
    ("laptop", r"laptop|macbook"),
    ("phone", r"phone (bill|service|plan)|cell(ular)? (service|plan|bill)|mobile plan|verizon|t-mobile"),
    ("internet", r"internet|wifi|wi-fi|broadband|comcast"),
    ("personal_device", r"\bphone\b|iphone|ipad|tablet|smart ?watch|apple watch|smart speaker|smart tv|router|mesh|extender|treadmill|walking pad"),
    ("coworking", r"cowork|co-work|wework|day pass|office space"),
    ("airfare", r"flight|airfare|airline|plane"),
    ("train", r"\btrain\b|amtrak|\brail\b|eurostar"),
    ("car_rental", r"rental car|car rental|rent a car|hertz|avis"),
    ("lodging", r"hotel|lodging|airbnb|motel|marriott|hilton"),
    ("rideshare", r"uber|lyft|taxi|\bcab\b|waymo|\bride\b"),
    ("parking", r"parking|toll"),
    ("meal", r"dinner|lunch|breakfast|meal|restaurant|coffee|drinks|catering|pizza|snacks"),
    ("swag", r"swag|stickers|t-shirts|giveaway|merch"),
    ("shipping", r"shipping|postage|fedex|\bups\b|usps|courier|customs"),
    ("books", r"\bbooks?\b|e-book|audiobook|kindle"),
    ("development", r"conference|training|tuition|certification|workshop|membership|\bdues\b|udemy|coursera"),
    ("software", r"subscription|saas|license|software|seat|\bplan\b|\bvpn\b"),
    ("equipment", r"monitor|keyboard|webcam|charger|desk|chair|headset|microphone|mouse|dock|equipment"),
    ("office_supplies", r"\bink\b|toner|paper|stapler|pens|notebook|supplies"),
]


def extract_stub(text: str) -> dict[str, dict]:
    text = (text or "").lower()
    kind = next((k for k, rx in _KINDS if re.search(rx, text)), None)
    return {
        "expense_kind": {"value": kind or "other", "p": 0.9 if kind else 0.5},
        "client_present": {"p": 0.9 if re.search(r"client|customer|cfo|ceo|prospect|investor|partner", text) else 0.5},
        "at_company_event": {"p": 0.9 if re.search(r"offsite|all-hands|company event|team event|team outing|team dinner|team lunch|kickoff|holiday party|team building", text) else 0.1},
        "traveling": {"p": 0.9 if re.search(r"\btrip\b|travel|flight|hotel|airbnb|on-?site|visiting|conference|out of town", text) else 0.1},
        "government_present": {"p": 0.9 if re.search(r"government|federal|agency|official|public sector|city of|state of|\bdod\b", text) else 0.1},
        "travel_class": {"value": next((c for c, rx in _CLASSES if re.search(rx, text)), "economy"), "p": 0.9},
        "gift_occasion": {"value": next((c for c, rx in _OCCASIONS if re.search(rx, text)), "life_event"), "p": 0.9},
        **{n: {"p": 0.9 if re.search(rx, text) else 0.1} for n, rx in _FLAGS.items()},
        "tip_over_20": {"p": 0.9 if any(int(x) > 20 for x in re.findall(r"(\d+)\s*%\s*tip", text)) else 0.1},
    }


_CLASSES = [("first", r"first class (flight|seat|ticket)|first class to"), ("business", r"business class"),
            ("premium", r"premium|economy plus|comfort plus|first class (train|rail)")]
_OCCASIONS = [("baby", r"baby|shower"), ("holiday", r"holiday|christmas|hanukkah|secret santa"),
              ("host", r"\bhost|stayed with|staying with")]
_FLAGS = {
    "international": r"international|overseas|abroad|london|paris|berlin|tokyo|amsterdam|dublin|singapore|sydney",
    "customer_trip": r"customer|client|prospect|speaking|speaker|keynote|conference|booth",
    "rental_car": r"rental|hertz|avis|enterprise",
    "mileage_and_fuel": r"mileage.*(gas|fuel|charg)|(gas|fuel|charg).*mileage",
    "cash_equivalent": r"gift card|giftcard|\bcash\b|prepaid card",
    "includes_fees": r"setup|set-up|installation|install fee|router|modem|activation|insurance|change fee",
    "whole_family_plan": r"whole family plan|entire family plan|family plan for all|all lines",
    "on_leave": r"on leave|parental leave|medical leave|sabbatical",
    "personal_travel": r"personal trip|personal travel|vacation",
    "companion_present": r"spouse|wife|husband|my partner|kids?\b|family|girlfriend|boyfriend",
    "commuting": r"commut|home to (the )?office|office to home|from home to work|to work\b",
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

    ponytail: still the original demo policy (rules 3.4-10.3), not the GitLab pack; the eval baseline
    needs a rewrite before the next eval run.

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
