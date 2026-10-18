"""Live Jev (Typesafe) extractor. Raises on any failure; the API layer decides fallbacks."""
import os
import time

import httpx

from engine.schema import FACTS

URL = "https://api.typesafe.ai/v1/systemone"

QUESTIONS = {  # the first three were tuned on api/bench_jev.py (45/45 kinds on the old 8-kind set); the GitLab kinds are untuned
    "expense_kind": {"type": "choice", "criteria": {
        "airfare": "An airline ticket or flight.",
        "train": "A train or rail ticket.",
        "car_rental": "A rental car, or fuel for one.",
        "lodging": "A hotel, motel, Airbnb or other place to sleep.",
        "rideshare": "A ground ride: taxi, cab, Uber, Lyft, Waymo or similar.",
        "parking": "Parking, tolls or public transport fares.",
        "meal": "Food or drink: a meal, dinner, lunch, breakfast, coffee, drinks, snacks, catering.",
        "internet": "Home or travel internet, wifi or broadband service.",
        "phone": "Monthly cell phone or mobile service.",
        "coworking": "A co-working space membership or day pass.",
        "equipment": "Home-office equipment: monitor, desk, chair, keyboard, mouse, webcam, headset, headphones, earbuds, AirPods, speaker for calls, charger, lamp, cables, dock.",
        "laptop": "A laptop, laptop replacement or laptop repair.",
        "personal_device": "A phone, tablet, smartwatch, smart speaker, smart TV, router, wifi extender or treadmill (not headphones or earbuds).",
        "office_supplies": "Consumable office supplies: ink, toner, paper, pens, notebooks, stapler.",
        "books": "A book, e-book or audiobook.",
        "development": "A conference, training, course, tuition, certification or professional membership dues.",
        "gift": "A gift or flowers for a team member.",
        "shipping": "Postage, shipping, courier or customs fees.",
        "software": "A software license, SaaS plan, app subscription or VPN.",
        "swag": "Swag, merchandise, stickers or giveaways.",
        "other": "Anything else: visas, permits, marketing spend, fees, business cards.",
    }},
    "client_present": {"type": "noul", "instructions":
        "Answer yes if a client, customer, partner, prospect or investor joined the employee at this meal, event or entertainment: for example a dinner with a client's CFO, drinks with prospects, a game, concert or golf with a customer or a client's team. Answer no for travel, lodging or rides to visit a client, for purchases with only coworkers or the employee alone, for outings with a spouse, romantic partner, family or friends, and for goods, software or fees."},
    "at_company_event": {"type": "noul", "instructions":
        "Answer yes if this purchase was for a company-organized event for employees: an offsite, all-hands, kickoff, team outing, team meal or team event, holiday party. Answer no for client meetings, external conferences, ordinary business travel, and individual or routine purchases."},
    "traveling": {"type": "noul", "instructions":
        "Answer yes if this expense was incurred while on a business trip away from home: during travel, at a conference, on a customer visit, at an offsite in another city. Answer no for purchases at home or in the employee's own city and for monthly services."},
    "government_present": {"type": "noul", "instructions":
        "Answer yes only if a government official, government employee or public-sector representative was among the people hosted at this meal or event. Answer no when no guests are mentioned or the guests are commercial clients, partners or coworkers."},
}


class JevError(Exception):
    pass


_CLIENT = httpx.Client(timeout=10.0)  # keep-alive: saves a TLS handshake (~15 ms) per call; thread-safe


def extract_with_meta(text: str) -> tuple[dict, dict]:
    key = os.environ.get("TYPESAFE_API_KEY")
    if not key:
        raise RuntimeError("TYPESAFE_API_KEY not set")
    t0 = time.perf_counter()
    try:
        r = _CLIENT.post(URL, headers={"Authorization": f"Bearer {key}"},
                         json={"model": "jev-latest", "state": text, "questions": QUESTIONS})
        r.raise_for_status()
        body = r.json()
    except httpx.HTTPStatusError as e:
        first = (e.response.text.strip().splitlines() or [""])[0][:200]
        raise JevError(f"Jev HTTP {e.response.status_code}: {first}") from None
    except (httpx.HTTPError, ValueError) as e:
        raise JevError(f"Jev request failed: {type(e).__name__}") from None
    latency = round((time.perf_counter() - t0) * 1000)
    try:
        a = body["answers"]
        facts = {n: {"p": float(a[n]["noul"])} for n, q in QUESTIONS.items() if q["type"] == "noul"}
        kind = a["expense_kind"]
        if kind["choice"] in FACTS["expense_kind"].values:
            facts = {"expense_kind": {"value": kind["choice"], "p": float(kind["confidence"])}, **facts}
    except (KeyError, TypeError, ValueError):
        raise JevError("Jev response had an unexpected shape") from None
    return facts, {"model": body.get("model"), "latency_ms": latency, "usage": body.get("usage"),
                   "probabilities": {k: v.get("probabilities") for k, v in a.items() if "probabilities" in v}}


def extract(text: str) -> dict[str, dict]:
    return extract_with_meta(text)[0]
