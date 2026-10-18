from engine.schema import FACTS

QUESTION_TEXT = {
    "client_present": "Was a client or partner present?",
    "at_company_event": "Was this a team event?",
    "traveling": "Was this during a business trip?",
    "government_present": "Was a government official among the guests?",
    "round_trip": "Is this a round trip?",
    "booked_via_navan": "Was it booked through Navan?",
    "approved_issue": "Is there an approved issue for it?",
    "receipt_attached": "Do you have the receipt?",
    "expense_kind": "What kind of expense is this?",
    "amount": "What is the amount in dollars?",
    "attendees": "How many people, including you?",
    "nights": "How many nights?",
    "days": "How many days does this cover?",
    "days_before_travel": "How many days before the trip is this booked?",
}

MERCHANT_CATEGORY = {
    "airfare": "4511 Airlines",
    "train": "4112 Passenger railways",
    "car_rental": "7512 Car rental",
    "lodging": "7011 Lodging",
    "rideshare": "4121 Taxicabs and rideshare",
    "parking": "7523 Parking lots and garages",
    "meal": "5812 Eating places",
    "internet": "4816 Computer network services",
    "phone": "4814 Telecommunication services",
    "coworking": "7399 Business services",
    "equipment": "5045 Computers and peripherals",
    "laptop": "5045 Computers and peripherals",
    "personal_device": "5732 Electronics stores",
    "office_supplies": "5111 Office supplies",
    "books": "5942 Book stores",
    "development": "8299 Educational services",
    "gift": "5947 Gift and novelty shops",
    "shipping": "4215 Courier services",
    "software": "5734 Computer software",
    "swag": "5999 Miscellaneous retail",
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
        ("at_company_event", False): "not a team event",
        ("at_company_event", True): "team event",
        ("client_present", True): "client present",
        ("client_present", False): "no client present",
        ("traveling", True): "while traveling",
        ("traveling", False): "not traveling",
        ("government_present", True): "government official present",
        ("round_trip", False): "one way",
        ("round_trip", True): "round trip",
        ("booked_via_navan", False): "booked outside Navan",
        ("approved_issue", False): "no approved issue",
    }
    units = {"attendees": "people", "nights": "nights", "days": "days"}
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
        if fact == "tenure_days":
            return f"{value} days since start date"
        if fact == "days_before_travel":
            return f"booked {value} days ahead"
        if fact in units:
            return f"{value} {units[fact]}"
    except TypeError:  # unhashable value
        pass
    return f"{fact} {value}"


def fix_phrase(step) -> str:
    fact, to = step.fact, step.to
    if fact == "pre_approved" and to is True:
        return "get manager pre-approval"
    if fact == "receipt_attached" and to is True:
        return "attach the receipt"
    if fact == "booked_via_navan" and to is True:
        return "book it through Navan"
    if fact == "approved_issue" and to is True:
        return "get an approved issue"
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
