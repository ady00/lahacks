"""Live Jev (Typesafe) extractor. Raises on any failure; the API layer decides fallbacks."""
import os
import time

import httpx

from engine.schema import FACTS

URL = "https://api.typesafe.ai/v1/systemone"

QUESTIONS = {
    "expense_kind": {"type": "choice", "criteria": {
        "meal": "Food or drink: a meal, dinner, lunch, coffee, catering.",
        "rideshare": "A taxi, Uber, Lyft or other ride.",
        "airfare": "An airline ticket or flight.",
        "hotel": "A hotel, lodging or Airbnb stay.",
        "software": "A software license, SaaS or app subscription.",
        "equipment": "Physical office or computer equipment such as a monitor, laptop or keyboard.",
        "entertainment": "Tickets or leisure: a concert, game, show, event admission.",
        "other": "Anything that fits none of the other kinds.",
    }},
    "client_present": {"type": "noul", "instructions":
        "Answer yes if a client, customer or prospect (for example a client's CFO) was present or hosted at this purchase."},
    "at_company_event": {"type": "noul", "instructions":
        "Answer yes if this was at a company-wide event such as an offsite, all-hands or team event."},
}


class JevError(Exception):
    pass


def extract_with_meta(text: str) -> tuple[dict, dict]:
    key = os.environ.get("TYPESAFE_API_KEY")
    if not key:
        raise RuntimeError("TYPESAFE_API_KEY not set")
    t0 = time.perf_counter()
    try:
        r = httpx.post(URL, headers={"Authorization": f"Bearer {key}"}, timeout=10.0,
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
