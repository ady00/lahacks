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
    "expense_kind": FactSpec("enum", ("meal", "rideshare", "airfare", "hotel", "software", "equipment", "entertainment", "other"), None, None, False, 0, False),
    "coded_account": FactSpec("enum", ("meals_50", "meals_100", "entertainment_0", "travel", "office", "other"), None, None, True, 1, True),
    "amount": FactSpec("real", None, 0, None, True, 3, False),
    "hour": FactSpec("int", None, 0, 23, False, 0, False),
    "days_since_purchase": FactSpec("int", None, 0, None, False, 0, False),
    "tenure_days": FactSpec("int", None, 0, None, False, 0, False),  # days since the employee record's start_date
    "receipt_attached": FactSpec("bool", None, None, None, True, 1, False),
    "pre_approved": FactSpec("bool", None, None, None, True, 2, False),
    "client_present": FactSpec("bool", None, None, None, False, 0, False),
    "at_company_event": FactSpec("bool", None, None, None, False, 0, False),
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
