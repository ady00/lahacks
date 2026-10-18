"""Fill the facts the extractor left open with one fast local `claude -p` call (Haiku by default).

Runs beside Jev on /check; api.cases keeps an answer only for a fact Jev or the keyword stub did not settle.
Never raises: no CLI, a timeout or junk output all mean {}.
"""
import json
import logging
import os
import shutil
import subprocess

from api.jev_live import QUESTIONS
from engine.schema import FACTS, validate_value

log = logging.getLogger(__name__)
SOURCE = "claude"
P = 0.95  # above POP_P_HI: an answer Claude gives counts as known, like a confident Jev answer

_KINDS = "; ".join(f"{k}: {v}" for k, v in QUESTIONS["expense_kind"]["criteria"].items())
_BOOLS = "\n".join(f"- {n}: true or false. {q['instructions']}" for n, q in QUESTIONS.items() if q["type"] == "noul")
PROMPT = f"""An employee typed a purchase request for an expense-policy check. Infer what the request implies, even when it is terse or misspelled (an AirPods purchase is a headset, so equipment). Reply with one JSON object and nothing else.

Keys, null when the request gives no basis to infer:
- expense_kind: one of {", ".join(FACTS["expense_kind"].values)}. Meanings: {_KINDS}
- amount: the price in US dollars as a number
{_BOOLS}

Request:
"""


def infer(text: str) -> dict[str, dict]:
    """-> probs-shaped guesses: enums {{value, p}}, bools {{p}}, amount {{value}}; each tagged source="claude"."""
    if not shutil.which("claude"):
        return {}
    try:
        r = subprocess.run(
            ["claude", "-p", "--model", os.environ.get("POP_INFER_MODEL", "haiku"), "--output-format", "text",
             "--no-session-persistence", "--tools", "", "--system-prompt", "Reply with JSON only.", PROMPT + text],
            capture_output=True, text=True, timeout=float(os.environ.get("POP_INFER_TIMEOUT", 20)))
        raw = r.stdout
        answers = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
    except Exception:  # noqa: BLE001 - a guess is optional; the case still proves without it
        log.warning("claude inference failed", exc_info=True)
        return {}
    return parse(answers)


def parse(answers: dict) -> dict[str, dict]:
    out = {}
    for name, value in (answers or {}).items():
        try:
            value = validate_value(name, value)
        except (KeyError, ValueError, TypeError):
            continue  # null, unknown key or an out-of-range value
        kind = FACTS[name].kind
        if kind == "bool":
            out[name] = {"p": P if value else round(1 - P, 2), "source": SOURCE}
        elif kind == "enum":
            out[name] = {"value": value, "p": P, "source": SOURCE}
        elif name == "amount":
            out[name] = {"value": value, "source": SOURCE}
    return out
