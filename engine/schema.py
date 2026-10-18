import math
from typing import Literal, NamedTuple


class FactSpec(NamedTuple):
    kind: Literal["enum", "real", "int", "bool"]
    values: tuple[str, ...] | None
    lo: int | None
    hi: int | None
    mutable: bool
    weight: int  # soft-constraint weight in fix; 0 for immutable facts
    derived: bool


FACTS: dict[str, FactSpec] = {
    "role": FactSpec("enum", ("employee", "contractor", "intern"), None, None, False, 0, False),
    # Navan expense types from GitLab's Global Travel & Expense Policy, merged where the rules are the same
    "expense_kind": FactSpec("enum", ("airfare", "train", "car_rental", "lodging", "rideshare", "parking", "meal", "internet", "phone",
                                      "coworking", "equipment", "laptop", "personal_device", "office_supplies", "books", "development",
                                      "gift", "shipping", "software", "swag", "other"), None, None, False, 0, False),
    "coded_account": FactSpec("enum", ("meals_50", "meals_100", "travel", "office", "other"), None, None, True, 1, True),
    "amount": FactSpec("real", None, 0, None, True, 3, False),
    "hour": FactSpec("int", None, 0, 23, False, 0, False),
    "days_since_purchase": FactSpec("int", None, 0, None, False, 0, False),
    "days_before_travel": FactSpec("int", None, 0, None, False, 0, False),  # booking lead time
    "tenure_days": FactSpec("int", None, 0, None, False, 0, False),  # days since the employee record's start_date
    "attendees": FactSpec("int", None, 1, None, False, 0, False),  # people at a meal, you included
    "nights": FactSpec("int", None, 1, None, False, 0, False),  # nights of lodging
    "days": FactSpec("int", None, 1, None, False, 0, False),  # days a per-day claim covers
    "receipt_attached": FactSpec("bool", None, None, None, True, 1, False),
    "pre_approved": FactSpec("bool", None, None, None, True, 2, False),
    "approved_issue": FactSpec("bool", None, None, None, True, 2, False),  # an approved G&D or IT issue is attached
    "booked_via_navan": FactSpec("bool", None, None, None, True, 1, False),
    "client_present": FactSpec("bool", None, None, None, False, 0, False),
    "at_company_event": FactSpec("bool", None, None, None, False, 0, False),
    "traveling": FactSpec("bool", None, None, None, False, 0, False),  # incurred on a business trip
    "round_trip": FactSpec("bool", None, None, None, False, 0, False),
    "government_present": FactSpec("bool", None, None, None, False, 0, False),  # a government official among the guests
}


def validate_value(name: str, value) -> object:
    """The API's one domain check: KeyError for an unknown fact, ValueError for a bad value."""
    spec = FACTS[name]
    number = isinstance(value, (int, float)) and not isinstance(value, bool)
    if spec.kind == "bool":
        if isinstance(value, bool):
            return value
        reason = "must be true or false"
    elif spec.kind == "enum":
        if isinstance(value, str) and value in spec.values:
            return value
        reason = f"must be one of {', '.join(spec.values)}"
    elif spec.kind == "real":
        if number and math.isfinite(value) and value > 0:
            return float(value)
        reason = "must be a number greater than 0"
    else:
        if number and float(value).is_integer() and (spec.lo is None or value >= spec.lo) and (spec.hi is None or value <= spec.hi):
            return int(value)
        reason = f"must be a whole number in {spec.lo}..{'' if spec.hi is None else spec.hi}"
    raise ValueError(f"{name}: {reason}")
