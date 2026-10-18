"""Dashboard signup: POST /employees creates a row /check accepts; GET /employees lists seed + new."""


def test_signup_creates_employee_that_check_accepts(client):
    e = client.post("/employees", json={"name": "Priya N", "role": "employee"}).json()
    assert e["employee_id"].startswith("e_") and len(e["employee_id"]) == 10
    assert e["manager_id"] == ""
    assert client.post("/check", json={"text": "Coffee $4", "employee_id": e["employee_id"]}).status_code == 200


def test_signup_rejects_unknown_role(client):
    assert client.post("/employees", json={"name": "X", "role": "cfo"}).status_code == 422


def test_list_employees_includes_seed_and_new(client):
    client.post("/employees", json={"name": "Aaron Z", "role": "intern", "manager_id": "e_manager"})
    names = [e["name"] for e in client.get("/employees").json()["employees"]]
    assert names == sorted(names) and "Dana Ortiz" in names and "Aaron Z" in names


# ---- worker record, tenure fact, probation rules, what applies to you ----
def test_signup_defaults_start_date_to_today_and_rejects_bad_date(client):
    e = client.post("/employees", json={"name": "New Hire", "role": "employee", "job_title": "Analyst", "department": "Finance"}).json()
    assert e["start_date"][:2] == "20" and e["job_title"] == "Analyst" and e["level"] == ""
    assert client.post("/employees", json={"name": "X", "role": "employee", "start_date": "yesterday"}).status_code == 422


def test_tenure_fact_fires_probation_rule_for_new_hire_only(client, monkeypatch):
    from api import cases
    monkeypatch.setattr(cases, "extract", lambda text: {"expense_kind": {"value": "equipment", "p": 0.99},
        "client_present": {"p": 0.05}, "at_company_event": {"p": 0.05}, "traveling": {"p": 0.05}, "equipment_off_list": {"p": 0.05}})
    new = client.post("/check", json={"text": "Monitor and a standing desk, $1,200", "employee_id": "e_newhire"}).json()
    assert new["facts"]["tenure_days"]["source"] == "employee" and new["facts"]["tenure_days"]["value"] < 365
    assert new["verdict"] == "compliant" and "EQUIP-1500" in new["applied"]   # first-year stipend covers it
    old = client.post("/check", json={"text": "Monitor and a standing desk, $1,200", "employee_id": "e_manager"}).json()
    assert [v["rule"] for v in old["violations"]] == ["EQUIP-500"] and old["facts"]["tenure_days"]["value"] > 365


def test_what_applies_to_you(client):
    assert client.get("/employees/nobody/rules").status_code == 404
    j = client.get("/employees/e_newhire/rules").json()
    by = {r["id"]: r for r in j["rules"]}
    assert j["employee"]["job_title"] == "Associate Product Manager" and j["facts"]["role"] == "employee"
    assert by["EQUIP-1500"]["applies"] and by["EQUIP-1500"]["days_left"] == 365 - j["facts"]["tenure_days"]
    assert by["GEN-receipt"]["applies"] and by["GEN-receipt"]["days_left"] is None
    assert not by["EQUIP-500"]["applies"]  # the yearly refresh cap starts after the first year
    m = {r["id"]: r for r in client.get("/employees/e_manager/rules").json()["rules"]}
    assert not m["EQUIP-1500"]["applies"] and m["EQUIP-500"]["applies"]
