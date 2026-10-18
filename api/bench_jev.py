"""Score live Jev's three facts on labeled messy purchase requests, and sweep the confidence thresholds.

python -m api.bench_jev            # current api.jev_live.QUESTIONS
python -m api.bench_jev --questions path/to/questions.json   # try a rewording before shipping it

Labels: expense_kind, client_present, at_company_event. None = too ambiguous to score; the probability is still shown.
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

from api import jev_live
from api.try_text import load_env

# text, expense_kind, client_present, at_company_event
CASES = [
    ("Dinner with Acme's CFO Thursday, about $48", "meal", True, False),
    ("Grabbed lunch with the design team, $22", "meal", False, False),
    ("Coffee with a coworker, $6.50", "meal", False, False),
    ("Pizza for the all-hands, $180", "meal", False, True),
    ("Drinks with two prospects from Stripe after the demo, $95", "meal", True, False),
    ("Catering for the offsite, $600", "meal", False, True),
    ("Lunch with a customer who's evaluating us, $70", "meal", True, False),
    ("Team dinner after shipping the release, $240", "meal", False, None),
    ("Breakfast at the hotel, solo, $18", "meal", False, False),
    ("Birthday cake for a teammate, $35", "meal", False, None),
    ("Dinner for 6 with investors from Sequoia, $520", "meal", None, False),
    ("Uber to the airport for the customer visit, $42", "rideshare", False, False),
    ("Lyft to the team offsite, $30", "rideshare", False, True),
    ("Cab from the hotel to the conference center, $25", "rideshare", False, False),
    ("Took a taxi home after working late, $38", "rideshare", False, False),
    ("Waymo to the client's office, $19", "rideshare", False, False),
    ("Flight to New York for the sales kickoff, $480", "airfare", False, True),
    ("Round trip to Denver to meet a prospect, $310", "airfare", False, False),
    ("United ticket SFO-ORD for the all-hands, $420", "airfare", False, True),
    ("Plane ticket to Austin for a conference, $265", "airfare", False, False),
    ("Hotel night in Chicago, $350", "hotel", False, False),
    ("Two nights at an Airbnb in Austin for the offsite, $400", "hotel", False, True),
    ("Marriott for the customer onsite, 3 nights, $780", "hotel", False, False),
    ("Annual Figma subscription, $144", "software", False, False),
    ("Renewing our Datadog plan, $650/month", "software", False, False),
    ("GitHub Copilot seat, $19", "software", False, False),
    ("A Notion license for the new hire, $10", "software", False, False),
    ("Zoom webinar add-on, $79", "software", False, False),
    ("Dell monitor for my desk, $300", "equipment", False, False),
    ("Standing desk from Uplift, $650", "equipment", False, False),
    ("Replacement laptop charger, $79", "equipment", False, False),
    ("Mechanical keyboard and a mouse, $150", "equipment", False, False),
    ("Webcam for the conference room, $120", "equipment", False, False),
    ("Concert ticket for a prospect, $150", "entertainment", True, False),
    ("Lakers tickets with a customer, $420", "entertainment", True, False),
    ("Golf round with the Acme team to close the deal, $280", "entertainment", True, False),
    ("Escape room for the team outing, $200", "entertainment", False, True),
    ("Broadway show with my partner, $240", "entertainment", False, False),
    ("Parking at the client's office, $14", "other", None, False),
    ("Conference registration for KubeCon, $1,200", "other", False, False),
    ("Printer paper and toner, $85", "other", False, False),
    ("Shipping a demo unit to a customer, $60", "other", False, False),
    ("Books for the onboarding library, $90", "other", False, False),
    ("Visa application fee for the London trip, $120", "other", False, False),
    ("Can I expense $45 of office supplies from Amazon?", "other", False, False),
]


def run(questions=None, hi=0.85, lo=0.15, verbose=True):
    if questions is not None:
        jev_live.QUESTIONS = questions
    rows, lat = [], []
    for text, kind, client, event in CASES:
        probs, meta = jev_live.extract_with_meta(text)
        lat.append(meta["latency_ms"])
        rows.append((text, kind, client, event, probs))
    kind_ok = sum(r[4].get("expense_kind", {}).get("value") == r[1] for r in rows)
    print(f"expense_kind: {kind_ok}/{len(rows)} correct   jev latency median {statistics.median(lat):.0f}ms p95 {sorted(lat)[int(len(lat)*.95)-1]}ms")
    for text, kind, _, _, probs in rows:
        got = probs.get("expense_kind", {})
        if verbose and got.get("value") != kind:
            print(f"  MISS kind: want {kind:13s} got {got.get('value')}@{got.get('p')}  :: {text}")
    for fact, idx in (("client_present", 2), ("at_company_event", 3)):
        scored = [(r[0], r[idx], r[4][fact]["p"]) for r in rows if r[idx] is not None]
        for h, l in ((hi, lo), (0.8, 0.2), (0.75, 0.25), (0.7, 0.3)):
            right = sum((p >= h) == want for _, want, p in scored if p >= h or p <= l)
            conf = sum(p >= h or p <= l for _, _, p in scored)
            print(f"{fact}: hi={h} lo={l}  confident {conf}/{len(scored)}  wrong {conf - right}  unknown {len(scored) - conf}")
        if verbose:
            for text, want, p in scored:
                if (p >= hi) != want and (p >= hi or p <= lo):
                    print(f"  WRONG {fact}: want {want} p={p}  :: {text}")
                elif lo < p < hi:
                    print(f"  unknown {fact}: want {want} p={p}  :: {text}")
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", help="JSON file with a QUESTIONS dict to try instead of the shipped one")
    ap.add_argument("--env", default=str(Path(__file__).resolve().parent.parent / ".env"))
    a = ap.parse_args(argv)
    load_env(Path(a.env))
    q = json.loads(Path(a.questions).read_text()) if a.questions else None
    run(q)


if __name__ == "__main__":
    sys.exit(main())
