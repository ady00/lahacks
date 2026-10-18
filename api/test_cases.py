from datetime import datetime
from zoneinfo import ZoneInfo

from api import cases

TS = datetime.now(ZoneInfo("America/Los_Angeles")).replace(hour=19, minute=30).isoformat()
# today at 19:30: days_since_purchase stays 0 so the receipt rules (which wait for the purchase) never wake up
# on a later date. Every /check below passes TS.
RIDE = lambda t: {"expense_kind": {"value": "rideshare", "p": 0.95}, "round_trip": {"p": 0.05}}


def test_demo_flow_check_approve_authorize(client, monkeypatch):
    monkeypatch.setattr(cases, "extract", RIDE)
    c = client.post("/check", json={"text": "Uber from LAX to the client's office, about $180.", "employee_id": "e_newhire", "timestamp": TS}).json()
    assert c["verdict"] == "violation" and [v["rule"] for v in c["violations"]] == ["RIDE-150"]
    assert c["facts"]["coded_account"] == {"value": "travel", "source": "rules", "p": None}
    assert c["facts"]["amount"]["source"] == "text" and c["awaiting_approval"] is True
    assert client.get("/cases", params={"awaiting_approval": "true"}).json()["cases"][0]["case_id"] == c["case_id"]
    assert client.post(f"/cases/{c['case_id']}/authorize").status_code == 409
    a = client.post(f"/cases/{c['case_id']}/approve", json={"approver": "e_manager", "approved": True}).json()
    assert a["verdict"] == "compliant" and a["awaiting_approval"] is False and a["approval"]["approver"] == "e_manager"
    auth = client.post(f"/cases/{c['case_id']}/authorize").json()
    assert auth["amount_limit"] == 180 and auth["merchant_category"] == "4121 Taxicabs and rideshare" and len(auth["proof_hash"]) == 64
    assert client.post(f"/cases/{c['case_id']}/authorize").json()["auth_id"] == auth["auth_id"]
    assert client.get(f"/cases/{c['case_id']}").json()["authorization"]["auth_id"] == auth["auth_id"]
    assert client.get("/cases", params={"awaiting_approval": "true"}).json()["cases"] == []


def test_answer_settles_an_undetermined_case(client, monkeypatch):
    monkeypatch.setattr(cases, "extract", lambda t: {"expense_kind": {"value": "rideshare", "p": 0.95}, "round_trip": {"p": 0.5}})
    c = client.post("/check", json={"text": "Lyft to the offsite and back", "employee_id": "e_intern", "amount": 180, "timestamp": TS}).json()
    assert c["verdict"] == "undetermined" and c["questions"][0]["fact"] == "round_trip"
    a = client.post(f"/cases/{c['case_id']}/answer", json={"fact": "round_trip", "value": True}).json()
    assert a["verdict"] == "compliant" and a["facts"]["round_trip"]["source"] == "answer"


def test_review_focus_edges(client):
    r = client.post("/check", json={"text": "dinner", "employee_id": "nobody", "timestamp": TS})
    assert r.status_code == 404 and r.json() == {"detail": "unknown employee"}
    assert client.post("/check", json={"text": "dinner", "employee_id": "e_newhire", "amount": -5, "timestamp": TS}).status_code == 422
    c = client.post("/check", json={"text": "Team dinner, not sure of the price", "employee_id": "e_newhire", "timestamp": TS}).json()
    assert c["verdict"] == "undetermined" and c["questions"][0]["fact"] == "amount" and "amount" in c["explanation"].lower()
    cid = c["case_id"]
    for bad in [{"fact": "colour", "value": True}, {"fact": "pre_approved", "value": True}, {"fact": "at_company_event", "value": "yes"},
                {"fact": "amount", "value": -1}, {"fact": "hour", "value": 99}, {"fact": "expense_kind", "value": "snack"}]:
        assert client.post(f"/cases/{cid}/answer", json=bad).status_code == 422, bad
    assert client.get("/cases/c_00000000").status_code == 404
    assert client.post("/cases/c_00000000/authorize").status_code == 404


def test_authorize_needs_a_known_amount(client):
    # the price never given: the $5,000 procurement line keeps it undetermined, so no card can be issued
    c = client.post("/check", json={"text": "Team dinner, not sure of the price", "employee_id": "e_newhire", "timestamp": TS}).json()
    client.post(f"/cases/{c['case_id']}/approve", json={"approver": "e_manager", "approved": True})
    a = client.post(f"/cases/{c['case_id']}/answer", json={"fact": "receipt_attached", "value": True}).json()
    assert a["verdict"] == "undetermined" and "amount" not in a["facts"] and a["questions"][0]["fact"] == "amount"
    r = client.post(f"/cases/{c['case_id']}/authorize")
    assert r.status_code == 409 and r.json()["detail"] == "not compliant"


def test_date_only_timestamp_leaves_hour_unknown(client):
    c = client.post("/check", json={"text": "Team dinner $20", "employee_id": "e_newhire", "timestamp": TS[:10]}).json()
    assert "hour" not in c["facts"]
    assert c["verdict"] == "compliant"   # GitLab's policy has no time-of-day rule, so the free hour decides nothing


def test_parse_amount():
    assert cases.parse_amount("Laptop $1,299.00 from Best Buy") == 1299.0
    assert cases.parse_amount("about $48.") == 48.0 and cases.parse_amount("$ 12.5 tip") == 12.5
    assert cases.parse_amount("$0 refund") is None and cases.parse_amount("no price") is None
    assert cases.parse_amount("$1.2k for a laptop") == 1200.0 and cases.parse_amount("about 48 bucks") == 48.0
    assert cases.parse_amount("1,200 USD registration") == 1200.0 and cases.parse_amount("3 clients to dinner for $320") == 320.0
    assert cases.parse_amount("$48 kombucha") == 48.0 and cases.parse_amount("2 tickets") is None


def test_answer_coerces_numbers(client):
    c = client.post("/check", json={"text": "Team dinner $20", "employee_id": "e_newhire", "timestamp": TS[:10]}).json()
    a = client.post(f"/cases/{c['case_id']}/answer", json={"fact": "hour", "value": 7})
    assert a.status_code == 200 and a.json()["facts"]["hour"] == {"value": 7, "source": "answer", "p": None}
    assert a.json()["verdict"] == "compliant"


def test_decide_transaction_takes_a_raw_csv_row():
    row = {"txn_id": "t_1", "company": "demo", "employee_id": "e_newhire", "vendor": "Nobu", "memo": "NOBU LA",
           "amount": "210", "timestamp": "2026-09-20T20:30:00-07:00", "qb_category": "Travel",
           "receipt_attached": "1", "receipt_date": "2026-09-21", "source": "intuit"}
    ext = {"expense_kind": {"value": "meal", "p": 0.95}, "client_present": {"p": 0.5}, "at_company_event": {"p": 0.05}}
    c = cases.decide_transaction(row, ext, False, {"role": "employee"})
    assert c["verdict"] == "violation" and {"IRS-meal"} <= {v["rule"] for v in c["violations"]}
    assert c["facts"]["days_since_purchase"]["value"] == 1 and c["facts"]["coded_account"]["source"] == "ledger"
    u = cases.decide_transaction({**row, "receipt_attached": "", "timestamp": "2026-09-20"}, None, False, None)
    assert "receipt_attached" not in u["facts"] and "hour" not in u["facts"] and "role" not in u["facts"]


def test_concurrent_polls_and_checks_never_crash():
    # subprocess: a segfault from a Z3 race fails this test instead of killing pytest
    code = f"""
import os, tempfile
from concurrent.futures import ThreadPoolExecutor
os.environ["POP_DB"] = os.path.join(tempfile.mkdtemp(), "t.db"); os.environ["POP_DATA_DIR"] = "/nonexistent"
from fastapi.testclient import TestClient
from api import cases
from api.main import app
from engine.keyword_baseline import extract_stub
cases.extract = extract_stub
TS = {TS!r}
with TestClient(app) as c:
    cid = c.post("/check", json={{"text": "Client dinner $48", "employee_id": "e_newhire", "timestamp": TS}}).json()["case_id"]
    def poll(_): return [c.get(f"/cases/{{cid}}").status_code for _ in range(40)]
    def check(_): return [c.post("/check", json={{"text": "Uber $30", "employee_id": "e_intern", "timestamp": TS}}).status_code for _ in range(10)]
    with ThreadPoolExecutor(8) as ex:
        out = [f.result() for f in [ex.submit(poll, i) for i in range(4)] + [ex.submit(check, i) for i in range(4)]]
assert all(s == 200 for o in out for s in o), out
"""
    import subprocess, sys
    env = {k: v for k, v in __import__("os").environ.items() if k != "TYPESAFE_API_KEY"}
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300, env=env)
    assert r.returncode == 0, (r.returncode, r.stderr[-2000:])


def test_reviewer_rejected_approval_stays_a_violation(client, monkeypatch):
    monkeypatch.setattr(cases, "extract", RIDE)
    c = client.post("/check", json={"text": "Uber to the client $180", "employee_id": "e_newhire", "timestamp": TS}).json()
    a = client.post(f"/cases/{c['case_id']}/approve", json={"approver": "e_manager", "approved": False}).json()
    assert a["verdict"] == "violation" and a["awaiting_approval"] is False and a["approval"]["approved"] is False
    r = client.post(f"/cases/{c['case_id']}/authorize")
    assert r.status_code == 409 and r.json()["detail"] == "not compliant"
    assert client.get("/cases", params={"awaiting_approval": "true"}).json()["cases"] == []
    assert client.post(f"/cases/{c['case_id']}/approve", json={"approver": "e_manager", "approved": True}).json()["verdict"] == "compliant"


def test_reviewer_responses_hide_stored_inputs(client):
    from api.models import Case
    want = set(Case.model_fields)
    c = client.post("/check", json={"text": "Client dinner $48", "employee_id": "e_newhire", "timestamp": TS}).json()
    cid = c["case_id"]
    got = [c, client.get(f"/cases/{cid}").json(), client.get("/cases").json()["cases"][0],
           client.post(f"/cases/{cid}/answer", json={"fact": "receipt_attached", "value": True}).json(),
           client.post(f"/cases/{cid}/approve", json={"approver": "e_manager", "approved": True}).json()]
    assert all(set(x) == want for x in got), [set(x) ^ want for x in got]


def test_reviewer_utc_and_bad_timestamps_unknown_case(client):
    c = client.post("/check", json={"text": "Client dinner $48", "employee_id": "e_newhire",
                                    "timestamp": "2026-10-17T19:30:00Z"}).json()
    assert c["facts"]["hour"]["value"] == 12   # 19:30 UTC is 12:30 in Los Angeles
    assert client.post("/check", json={"text": "x", "employee_id": "e_newhire", "timestamp": "garbage"}).status_code == 422
    assert client.post("/cases/c_00000000/answer", json={"fact": "pre_approved", "value": True}).status_code == 404
    assert client.post("/cases/c_00000000/approve", json={"approver": "e_manager", "approved": True}).status_code == 404


def test_keyword_fallback_facts_are_labelled_text(client, monkeypatch):
    import sys
    monkeypatch.setattr(cases, "extract", cases._EXTRACT)       # undo the fake: the real chain runs
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setitem(sys.modules, "extract.jev", None)       # Person B's module unimportable even once it lands
    c = client.post("/check", json={"text": "Client dinner with Acme's CFO, about $48.", "employee_id": "e_newhire", "timestamp": TS}).json()
    assert c["facts"]["expense_kind"] == {"value": "meal", "source": "text", "p": 0.9}
    assert c["facts"]["client_present"]["source"] == "text"
    a = client.post(f"/cases/{c['case_id']}/approve", json={"approver": "e_manager", "approved": True}).json()
    assert a["facts"]["expense_kind"]["source"] == "text"       # re-proving keeps the label


def test_fixture_extractor_counts_as_jev(client):
    c = client.post("/check", json={"text": "Client dinner $48", "employee_id": "e_newhire", "timestamp": TS}).json()
    assert c["facts"]["expense_kind"] == {"value": "meal", "source": "jev", "p": 0.97}


def test_miles_are_read_from_the_text():
    from api.cases import parse_miles
    assert parse_miles("Drove 120 miles to the client site, $95") == 120
    assert parse_miles("about 12 mi round trip") == 12 and parse_miles("Uber, $40") is None


def test_ledger_row_falls_back_to_the_keyword_reading_for_facts_the_stored_extraction_never_asked():
    # data/extractions.jsonl predates the commuting question; a plain airport ride must not hang on it
    from api.cases import decide_transaction
    row = {"txn_id": "t_x", "company": "demo", "employee_id": "e_newhire", "vendor": "Uber", "memo": "Uber to the airport for the Denver trip",
           "amount": "62", "timestamp": "2026-10-10T08:00:00", "qb_category": "Travel", "receipt_attached": "1", "receipt_date": ""}
    c = decide_transaction(row, {"expense_kind": {"value": "rideshare", "p": 1.0}, "at_company_event": {"p": 0.05}, "client_present": {"p": 0.05}}, False, None)
    assert c["facts"]["commuting"] == {"value": False, "source": "text", "p": 0.1}
    assert c["facts"]["expense_kind"]["source"] == "jev" and "commuting" not in [q["fact"] for q in c["questions"]]
