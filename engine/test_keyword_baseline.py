from engine.keyword_baseline import CODED_FALLBACK, extract_stub, keyword_verdict, txn_row

ROW = dict(txn_id="t1", company="demo", employee_id="e_newhire", vendor="Uber", memo="UBER TRIP", amount="18.5",
           timestamp="2026-09-30T08:10:00-07:00", qb_category="Travel", receipt_attached="1", receipt_date="2026-10-01", source="intuit")


def test_keyword_verdict_takes_a_raw_csv_row():
    assert keyword_verdict(ROW)["verdict"] == "compliant"
    nobu = {**ROW, "memo": "NOBU LA dinner", "amount": "210", "timestamp": "2026-09-20T20:30:00-07:00", "receipt_date": "2026-09-21"}
    assert {"3.4", "IRS-meal"} <= set(keyword_verdict(nobu)["rules"])
    assert "3.4" not in keyword_verdict(nobu, pre_approved=True)["rules"]


def test_no_receipt_old_purchase_and_date_only_hour_unknown():
    old = {**ROW, "memo": "team dinner", "amount": "20", "timestamp": "2020-01-01", "receipt_attached": "0", "receipt_date": "", "qb_category": "Meals"}
    r = keyword_verdict(old)
    assert "IRS-receipt-60" in r["rules"] and "6.2" not in r["rules"]
    assert r["verdict"] == "violation"


def test_extract_stub_table():
    e = extract_stub("UBER TRIP with the CFO")
    assert e["expense_kind"] == {"value": "rideshare", "p": 0.9}
    assert e["client_present"] == {"p": 0.9} and e["at_company_event"] == {"p": 0.1}
    e = extract_stub("misc thing")
    assert e["expense_kind"] == {"value": "other", "p": 0.5} and e["client_present"]["p"] == 0.5
    assert extract_stub("Company Event lunch")["at_company_event"]["p"] == 0.9
    assert extract_stub("")["expense_kind"]["value"] == "other"


def test_txn_row_normalizes_csv_and_db_rows_without_mutating():
    raw = {**ROW, "receipt_attached": "", "receipt_date": "", "employee_id": "", "qb_category": ""}
    t = txn_row(raw)
    assert t["amount"] == 18.5 and t["receipt_attached"] is None and t["receipt_date"] is None
    assert t["employee_id"] is None and t["qb_category"] is None and t["vendor"] == "Uber"
    assert raw["amount"] == "18.5" and raw["receipt_attached"] == ""
    for v, want in [("1", True), (1, True), ("true", True), ("0", False), (0, False), ("false", False), (None, None)]:
        assert txn_row({**ROW, "receipt_attached": v})["receipt_attached"] is want
    db = txn_row({**ROW, "amount": 5, "receipt_attached": None, "receipt_date": None, "employee_id": None})
    assert db["amount"] == 5.0 and db["receipt_attached"] is None


def test_coded_fallback():
    assert CODED_FALLBACK == {"Meals": "meals_50", "Travel": "travel", "Office": "office", "Entertainment": "other"}


# reviewer edge cases
def test_reviewer_thresholds_are_exact():
    meal = {**ROW, "memo": "lunch", "qb_category": "Meals"}
    assert keyword_verdict({**meal, "amount": "35"})["rules"] == []
    assert keyword_verdict({**meal, "amount": "35.01"})["rules"] == ["3.4"]
    bare = {**ROW, "memo": "misc", "qb_category": "", "receipt_attached": "0", "receipt_date": ""}
    assert "IRS-receipt-75" in keyword_verdict({**bare, "amount": "75"})["rules"]
    assert "IRS-receipt-75" not in keyword_verdict({**bare, "amount": "74.99"})["rules"]


def test_reviewer_hour_is_los_angeles_and_unknown_for_date_only():
    dinner = {**ROW, "memo": "dinner", "qb_category": "Meals", "amount": "20", "receipt_date": "2026-10-01"}
    assert "6.1" in keyword_verdict({**dinner, "timestamp": "2026-10-01T06:30:00Z"})["rules"]   # 23:30 LA
    assert "6.1" in keyword_verdict({**dinner, "timestamp": "2026-09-30T23:10:00"})["rules"]    # naive = LA
    assert "6.2" not in keyword_verdict({**dinner, "timestamp": "2026-09-30T13:10:00Z"})["rules"]  # 06:10 LA
    r = keyword_verdict({**dinner, "timestamp": "2026-09-30"})["rules"]
    assert "6.1" not in r and "6.2" not in r


def test_reviewer_unicode_memo_repeat_call_no_mutation():
    row = {**ROW, "memo": "café dîner ☕ coffee", "qb_category": "Meals", "amount": "12"}
    before = dict(row)
    a, b = keyword_verdict(row), keyword_verdict(row)
    assert a == b == {"verdict": "compliant", "rules": []} and row == before
    assert extract_stub("CAFÉ COFFEE")["expense_kind"]["value"] == "meal"
