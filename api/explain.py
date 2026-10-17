from engine.schema import FACTS

QUESTION_TEXT = {
    "client_present": "Was a client present?",
    "at_company_event": "Was this at a company-wide event?",
    "receipt_attached": "Do you have the receipt?",
    "expense_kind": "What kind of expense is this?",
    "amount": "What is the amount in dollars?",
}

MERCHANT_CATEGORY = {
    "meal": "5812 Eating places",
    "rideshare": "4121 Taxicabs and rideshare",
    "airfare": "4511 Airlines",
    "hotel": "7011 Lodging",
    "software": "5734 Computer software",
    "equipment": "5045 Computers and peripherals",
    "entertainment": "7922 Entertainment",
    "other": "5999 Miscellaneous retail",
}


def question(fact: str, p: float | None) -> dict:
    spec = FACTS.get(fact)
    options = list(spec.values) if spec and spec.kind == "enum" else None
    return {"fact": fact, "text": QUESTION_TEXT.get(fact, f"What is {fact}?"), "p": p, "options": options}


def _money(x) -> str:
    return f"${x:.2f}".removesuffix(".00") if isinstance(x, (int, float)) and not isinstance(x, bool) else f"${x}"


def phrase(fact: str, value) -> str:
    table = {
        ("pre_approved", False): "no pre-approval",
        ("pre_approved", True): "pre-approved",
        ("receipt_attached", False): "no receipt",
        ("at_company_event", False): "not a company event",
        ("client_present", True): "client present",
    }
    try:
        if fact == "amount":
            return f"amount {_money(value)}"
        if (fact, value) in table:
            return table[(fact, value)]
        if fact == "coded_account":
            return f"coded {value}"
        if fact == "role":
            return f"role {value}"
        if fact == "expense_kind":
            return str(value)
        if fact == "hour":
            return f"at {value}:00"
        if fact == "days_since_purchase":
            return f"{value} days ago"
    except TypeError:  # unhashable value
        pass
    return f"{fact} {value}"


def fix_phrase(step) -> str:
    fact, to = step.fact, step.to
    if fact == "pre_approved" and to is True:
        return "get manager pre-approval"
    if fact == "receipt_attached" and to is True:
        return "attach the receipt"
    if fact == "coded_account":
        return f"code it as {to}"
    if fact == "amount":
        return f"keep it at or under {_money(to)}"
    return f"set {fact} to {to}"


def explain(decision, by_id: dict, unknown: list[str]) -> str:
    v, facts, out = decision.verdict, decision.facts, []
    for x in v.violations:
        text = by_id[x.rule].text.rstrip(".")
        out.append(f"{text} (rule {x.rule}): {', '.join(phrase(f, facts.get(f)) for f in x.because)}.")
    if v.status == "violation":
        if decision.fix is None:
            out.append("No change you control makes this compliant.")
        elif decision.fix:
            out.append("Fix: " + ", ".join(fix_phrase(s) for s in decision.fix) + ".")
    if v.status == "compliant":
        out.append(f"Compliant: rules {', '.join(v.applied)} hold." if v.applied else "Compliant: no rule applies.")
    if v.status == "undetermined":
        first = (decision.questions or unknown or [None])[0]
        out.append("Depends on: " + (QUESTION_TEXT.get(first, f"What is {first}?") if first else "a fact we don't know yet."))
    out += [f"Post it as {facts[f]} ({rid})." for f, rid in decision.derived.items()]
    return " ".join(out)
