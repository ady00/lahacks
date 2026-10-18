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
