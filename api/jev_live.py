"""Live Jev (Typesafe) extractor. Raises on any failure; the API layer decides fallbacks."""
import os
import time

import httpx

from engine.schema import FACTS

URL = "https://api.typesafe.ai/v1/systemone"

QUESTIONS = {  # wording tuned on api/bench_jev.py: 45/45 kinds, 0 confidently-wrong booleans at 0.85/0.15
    "expense_kind": {"type": "choice", "criteria": {
        "meal": "Food or drink: a meal, dinner, lunch, breakfast, coffee, drinks, snacks, cake, catering.",
        "rideshare": "A ground ride: taxi, cab, Uber, Lyft, Waymo or similar.",
        "airfare": "An airline ticket or flight.",
        "hotel": "A hotel, lodging or Airbnb stay.",
        "software": "A software license, SaaS plan, seat or app subscription.",
        "equipment": "Physical computer or office equipment: monitor, laptop, charger, keyboard, webcam, desk.",
        "entertainment": "Leisure or recreation: a concert, sports game, show, golf, escape room or similar outing.",
        "other": "Anything else: conference or event registration, parking, shipping, fees, office supplies, books, paper.",
    }},
    "client_present": {"type": "noul", "instructions":
        "Answer yes if a client, customer, prospect or investor joined the employee at this meal, event or entertainment: for example a dinner with a client's CFO, drinks with prospects, a game, concert or golf with a customer or a client's team. Answer no for travel, lodging or rides to visit a client, for purchases with only coworkers or the employee alone, and for goods, software or fees."},
    "at_company_event": {"type": "noul", "instructions":
        "Answer yes if this purchase was for a company-organized event for employees: an offsite, all-hands, kickoff, team outing or team event, holiday party. Answer no for client meetings, external conferences, ordinary business travel, and individual or routine purchases."},
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
        facts = {"client_present": {"p": float(a["client_present"]["noul"])},
                 "at_company_event": {"p": float(a["at_company_event"]["noul"])}}
        kind = a["expense_kind"]
        if kind["choice"] in FACTS["expense_kind"].values:
            facts = {"expense_kind": {"value": kind["choice"], "p": float(kind["confidence"])}, **facts}
    except (KeyError, TypeError, ValueError):
        raise JevError("Jev response had an unexpected shape") from None
    return facts, {"model": body.get("model"), "latency_ms": latency, "usage": body.get("usage"),
                   "probabilities": {k: v.get("probabilities") for k, v in a.items() if "probabilities" in v}}


def extract(text: str) -> dict[str, dict]:
    return extract_with_meta(text)[0]
