import json
from contextlib import closing

from api import cases, db


def test_init_twice_and_seed_employees(tmp_path):
    conn = db.connect(tmp_path / "t.db"); db.init(conn); db.init(conn)
    db.load_data_dir(conn, tmp_path / "nodata")
    assert db.employee(conn, "e_intern")["role"] == "intern"
    assert isinstance(db.employee(conn, "e_intern"), dict) and db.employee(conn, "zzz") is None


def test_connect_reads_env_at_call_time(tmp_path, monkeypatch):
    monkeypatch.setenv("POP_DB", str(tmp_path / "env.db"))
    with closing(db.connect()) as conn:
        assert db.employee(conn, "e_manager")["name"] == "Dana Ortiz"
    assert (tmp_path / "env.db").exists()


def test_load_data_dir_reads_b_files(tmp_path):
    (tmp_path / "transactions.csv").write_text("txn_id,company,employee_id,vendor,memo,amount,timestamp,qb_category,receipt_attached,receipt_date,source\n"
        "t1,demo,e_newhire,Uber,UBER TRIP,18.5,2026-09-30T08:10:00-07:00,Travel,1,2026-10-01,intuit\n"
        "t2,demo,e_newhire,Cafe,LUNCH,9,2026-09-30T12:00:00-07:00,Meals,,,intuit\n")
    (tmp_path / "extractions.jsonl").write_text('{"txn_id": "t1", "facts": {"expense_kind": {"value": "rideshare", "p": 0.95}}}\n')
    (tmp_path / "approvals.csv").write_text("txn_id,approver,approved_at\nt1,e_manager,2026-09-29T10:00:00-07:00\n")
    conn = db.connect(tmp_path / "t.db"); db.init(conn); db.load_data_dir(conn, tmp_path)
    rows = {r["txn_id"]: r for r in db.list_transactions(conn, company="demo")}
    row = rows["t1"]
    assert row["amount"] == 18.5 and json.loads(row["extraction_json"])["expense_kind"]["value"] == "rideshare"
    assert row["receipt_attached"] == 1 and rows["t2"]["receipt_attached"] is None
    assert rows["t2"]["extraction_json"] is None
    assert db.txn_pre_approved(conn, "t1") is True and db.txn_pre_approved(conn, "t2") is False
    assert db.count_transactions(conn) == 2 and db.count_transactions(conn, "other") == 0
    # reload: file approvals not duplicated, case approvals survive, verdicts of unchanged rows survive
    db.add_approval(conn, "c1", None, "e_manager", True, "now")
    db.put_verdict(conn, "t1", "v1", {"verdict": "compliant"})
    db.load_data_dir(conn, tmp_path)
    assert conn.execute("SELECT COUNT(*) FROM approvals WHERE case_id IS NULL").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM approvals WHERE case_id = 'c1'").fetchone()[0] == 1
    assert db.get_verdict(conn, "t1", "v1")["verdict"] == "compliant"


def test_upsert_deletes_verdicts_only_when_row_changes(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    row = {"txn_id": "t1", "company": "demo", "employee_id": "e_newhire", "memo": "m", "amount": 5.0, "source": "case"}
    db.upsert_transactions(conn, [row])  # missing columns -> NULL
    assert db.list_transactions(conn)[0]["coded_account"] is None
    db.put_verdict(conn, "t1", "v1", {"verdict": "compliant", "x": 1})
    db.upsert_transactions(conn, [dict(row)])  # identical -> kept
    assert db.get_verdict(conn, "t1", "v1") == {"txn_id": "t1", "policy_version": "v1", "verdict": "compliant",
                                                "case": {"verdict": "compliant", "x": 1}}
    db.upsert_transactions(conn, [dict(row, amount=6.0)])  # changed -> dropped
    assert db.get_verdict(conn, "t1", "v1") is None
    assert db.list_transactions(conn)[0]["amount"] == 6.0


def test_cases_and_approvals(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    case = {"case_id": "c1", "created_at": "2026-10-01T00:00:00", "employee_id": "e_newhire", "text": "lunch $12",
            "policy_version": "v1", "awaiting_approval": True, "facts": {"amount": {"value": 12.0, "p": 1.0}}}
    db.put_case(conn, case, {"receipt_attached": True})
    db.put_case(conn, dict(case, case_id="c2", awaiting_approval=False, facts={}), {})
    assert db.get_case(conn, "c1") == case and db.get_case(conn, "nope") is None
    assert db.get_answers(conn, "c1") == {"receipt_attached": True} and db.get_answers(conn, "nope") == {}
    assert [c["case_id"] for c in db.list_cases(conn)] == ["c1", "c2"]
    assert [c["case_id"] for c in db.list_cases(conn, awaiting_approval=True)] == ["c1"]
    assert [c["case_id"] for c in db.list_cases(conn, awaiting_approval=False)] == ["c2"]
    row = conn.execute("SELECT amount, awaiting_approval FROM cases WHERE case_id='c1'").fetchone()
    assert row["amount"] == 12.0 and row["awaiting_approval"] == 1
    assert db.case_approval(conn, "c1") is None
    db.add_approval(conn, "c1", None, "e_manager", False, "t1")
    db.add_approval(conn, "c1", None, "e_manager", True, "t2")
    assert db.case_approval(conn, "c1")["approved"] == 1 and db.case_approval(conn, "c1")["at"] == "t2"
    db.record_policy(conn, "v1", {"rules": []}); db.record_policy(conn, "v1", {"rules": []})
    assert conn.execute("SELECT COUNT(*) FROM policy_versions").fetchone()[0] == 1


HEADER = "txn_id,company,employee_id,vendor,memo,amount,timestamp,qb_category,receipt_attached,receipt_date,source\n"


def test_reviewer_reload_idempotent_unicode_and_extraction_change(tmp_path):
    (tmp_path / "transactions.csv").write_text(HEADER
        + "t1,demo,e_newhire,Café Ñ,CAFÉ ☕ LUNCH,35,2026-09-30T12:00:00,Meals,1,,intuit\n"
        + "t2,demo,e_newhire,Uber,UBER,18.5,2026-09-30,Travel,0,,intuit\n", encoding="utf-8")
    (tmp_path / "extractions.jsonl").write_text('{"txn_id": "t1", "facts": {"expense_kind": {"value": "meal", "p": 0.9}}}\n\n')
    conn = db.connect(tmp_path / "t.db")
    db.load_data_dir(conn, tmp_path)
    db.put_verdict(conn, "t1", "v1", {"verdict": "compliant"}); db.put_verdict(conn, "t2", "v1", {"verdict": "violation"})
    db.load_data_dir(conn, tmp_path); db.load_data_dir(conn, tmp_path)  # repeated reload: nothing churns
    assert conn.execute("select count(*) from verdicts").fetchone()[0] == 2
    t1 = db.list_transactions(conn)[0]
    assert t1["memo"] == "CAFÉ ☕ LUNCH" and t1["timestamp"] == "2026-09-30T12:00:00" and t1["amount"] == 35.0
    # extraction changes for t1 only -> only t1's verdict is dropped
    (tmp_path / "extractions.jsonl").write_text('{"txn_id": "t1", "facts": {"expense_kind": {"value": "meal", "p": 0.99}}}\n')
    db.load_data_dir(conn, tmp_path)
    assert db.get_verdict(conn, "t1", "v1") is None and db.get_verdict(conn, "t2", "v1")["verdict"] == "violation"


def test_reviewer_task9_and_task8_shaped_rows(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.upsert_transactions(conn, [])  # empty list is a no-op
    task9 = dict(txn_id="t1", company="demo", employee_id="e_newhire", vendor="Uber", memo="UBER TRIP", amount=18.5,
                 timestamp="2026-09-30T08:10:00-07:00", qb_category="Travel", receipt_attached=1, receipt_date="2026-10-01",
                 source="intuit", extraction_json=json.dumps({"expense_kind": {"value": "rideshare", "p": 0.95}}))
    auth = dict(txn_id="c_deadbeef", company="demo", employee_id="e_newhire", memo="Team dinner", amount=120,
                timestamp="2026-09-20T20:30:00-07:00", source="case", coded_account="meals_50")
    db.upsert_transactions(conn, [task9, auth])
    for t in ("t1", "c_deadbeef"):
        db.put_verdict(conn, t, "v1", {"verdict": "compliant"})
    db.upsert_transactions(conn, [dict(task9), dict(auth)])  # same rows again (idempotent authorize)
    assert conn.execute("select count(*) from verdicts").fetchone()[0] == 2
    db.load_data_dir(conn, tmp_path / "missing")  # reload with no files leaves case rows alone
    assert db.list_transactions(conn, limit=1, offset=1)[0]["coded_account"] == "meals_50"
    assert db.count_transactions(conn, "demo") == 2 and db.get_verdict(conn, "nope", "v1") is None
    assert db.list_transactions(conn, limit=0) == [] and db.list_transactions(conn, offset=5) == []


def test_reviewer_per_request_connection_under_testclient(tmp_path, monkeypatch):
    import threading
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    monkeypatch.setenv("POP_DB", str(tmp_path / "srv.db"))
    app = FastAPI()

    @app.get("/e/{eid}")
    def e(eid: str):
        with closing(db.connect()) as conn:
            db.add_approval(conn, None, eid, "e_manager", True, "now")
            return db.employee(conn, eid) or {}

    client = TestClient(app)
    errs = []

    def hit():
        try:
            for _ in range(10):
                assert client.get("/e/e_intern").json()["role"] == "intern"
        except Exception as x:  # noqa: BLE001
            errs.append(x)
    ts = [threading.Thread(target=hit) for _ in range(4)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert errs == []
    with closing(db.connect()) as conn:  # opened in the test thread, sees the route threads' commits
        assert conn.execute("select count(*) from approvals").fetchone()[0] == 40


def test_load_skips_bad_rows_and_bad_json_never_raises(tmp_path):
    H = "txn_id,company,employee_id,vendor,memo,amount,timestamp,qb_category,receipt_attached,receipt_date,source\n"
    ok = "ok,demo,,V,M,5,2026-09-30,Travel,,,intuit\n"
    (tmp_path / "transactions.csv").write_text(H + ok + "a,demo,,V,M,abc,2026-09-30,Travel,1,,intuit\n"
        "b,demo,,V,M,5,yesterday,Travel,1,,intuit\n,demo,,V,M,5,2026-09-30,Travel,1,,intuit\n"
        "ok,other,,V,M,5,2026-09-30,Travel,1,,intuit\n")
    (tmp_path / "extractions.jsonl").write_text('not json\n{"facts": {}}\n[1]\n')
    conn = db.connect(tmp_path / "t.db")
    r = db.load_data_dir(conn, tmp_path)
    assert (r["transactions"], r["extractions"]) == (1, 0)
    assert [s["reason"] for s in r["skipped"]] == ["amount must be > 0 (refunds and credits are not audited)",
        "bad timestamp", "missing txn_id", "txn_id collision"] and r["skipped"][2]["txn_id"] == ""
    row = db.list_transactions(conn)[0]
    assert row["employee_id"] is None and row["receipt_attached"] is None
    assert cases.decide_transaction(row, None, False, None)["verdict"]  # no employee: no exception
    assert db.load_data_dir(conn, tmp_path / "missing")["skipped"] == []


def test_reviewer_crlf_quoted_multiline_memo_z_timestamp_extra_column(tmp_path):
    H = "txn_id,company,employee_id,vendor,memo,amount,timestamp,qb_category,receipt_attached,receipt_date,source,extra\r\n"
    (tmp_path / "transactions.csv").write_text(H + 't1,demo,e_newhire,Café,"DINNER, 東京\r\nline 2",18.5,'
                                               "2026-09-30T15:10:00Z,Travel,1,,intuit,zzz\r\n", newline="")
    conn = db.connect(tmp_path / "t.db")
    assert db.load_data_dir(conn, tmp_path)["transactions"] == 1
    row = db.list_transactions(conn)[0]
    assert row["memo"] == "DINNER, 東京\r\nline 2" and row["amount"] == 18.5
    assert cases.decide_transaction(row, None, False, db.employee(conn, "e_newhire"))["facts"]["hour"]["value"] == 8


def test_reviewer_approvals_reloaded_twice_no_duplicates_and_approve_rows_survive(tmp_path):
    (tmp_path / "approvals.csv").write_text("txn_id,approver,approved_at\nt1,e_manager,2026-09-29\n")
    conn = db.connect(tmp_path / "t.db"); db.init(conn)
    db.add_approval(conn, "c_1", "t9", "e_manager", True, "2026-09-30")
    for _ in range(2):
        assert db.load_data_dir(conn, tmp_path)["approvals"] == 1
    assert [tuple(r) for r in conn.execute("select case_id, txn_id from approvals order by id")] == [("c_1", "t9"), (None, "t1")]


def test_receipt_flag_variants_and_bom(tmp_path):
    H = "txn_id,company,employee_id,vendor,memo,amount,timestamp,qb_category,receipt_attached,receipt_date,source\n"
    flags = {"a": "TRUE", "b": "1.0", "c": "yes", "d": "0", "e": "No", "f": "", "g": "maybe"}
    (tmp_path / "transactions.csv").write_text(
        "﻿" + H + "".join(f"{k},demo,,V,M,5,2026-09-30,Travel,{v},,intuit\n" for k, v in flags.items()), encoding="utf-8")
    (tmp_path / "employees.csv").write_text("﻿employee_id,name,role,manager_id\nz1,Zed,intern,\n", encoding="utf-8")
    conn = db.connect(tmp_path / "t.db")
    r = db.load_data_dir(conn, tmp_path)
    assert r["skipped"] == [] and r["transactions"] == 7 and r["employees"] == 1
    got = {x["txn_id"]: x["receipt_attached"] for x in db.list_transactions(conn)}
    assert got == {"a": 1, "b": 1, "c": 1, "d": 0, "e": 0, "f": None, "g": None}


def test_concurrent_first_connections_are_race_safe(tmp_path):
    import threading
    n, errs = 16, []
    for rnd in range(20):  # the race window is small; many fresh DBs make it near-certain
        path, barrier = tmp_path / f"race{rnd}.db", threading.Barrier(n)

        def first():
            try:
                barrier.wait()
                db.connect(path).close()
            except Exception as x:  # noqa: BLE001
                errs.append(repr(x))
        ts = [threading.Thread(target=first) for _ in range(n)]
        [t.start() for t in ts]; [t.join() for t in ts]
        assert errs == []
        with closing(db.connect(path)) as conn:
            assert conn.execute("select count(*) from employees").fetchone()[0] == 4


def test_reviewer_employees_csv_beats_seed_across_reconnects(tmp_path):
    (tmp_path / "employees.csv").write_text(
        "employee_id,name,role,manager_id\ne_manager,Zoë Ünïcode,manager,\ne_intern,Ria P,employee,e_manager\n",
        encoding="utf-8")
    p = tmp_path / "t.db"
    with closing(db.connect(p)) as conn:
        db.load_data_dir(conn, tmp_path)
    for _ in range(3):  # repeated connects (re-run init) must not revert B's rows to the seed
        with closing(db.connect(p)) as conn:
            assert db.employee(conn, "e_manager") == {"employee_id": "e_manager", "name": "Zoë Ünïcode",
                                                      "role": "manager", "manager_id": ""}
            assert db.employee(conn, "e_intern")["role"] == "employee"
            assert conn.execute("select count(*) from employees").fetchone()[0] == 4


def test_reviewer_seed_not_reinserted_when_table_has_only_b_rows(tmp_path):
    p = tmp_path / "t.db"
    with closing(db.connect(p)) as conn:
        conn.execute("DELETE FROM employees")
        conn.execute("INSERT INTO employees VALUES ('z1','Zed','intern','')")
        conn.commit()
    with closing(db.connect(p)) as conn:
        assert [r[0] for r in conn.execute("select employee_id from employees")] == ["z1"]


def test_reviewer_concurrent_connects_after_reload_keep_b_rows(tmp_path):
    import threading
    (tmp_path / "employees.csv").write_text("employee_id,name,role,manager_id\ne_manager,B Boss,manager,\n",
                                            encoding="utf-8")
    p = tmp_path / "t.db"
    with closing(db.connect(p)) as conn:
        db.load_data_dir(conn, tmp_path)
    b, errs = threading.Barrier(8), []

    def go():
        try:
            b.wait()
            with closing(db.connect(p)) as c:
                db.put_verdict(c, "t1", "v1", {"verdict": "pass"})
        except Exception as x:  # noqa: BLE001
            errs.append(repr(x))
    ts = [threading.Thread(target=go) for _ in range(8)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert errs == []
    with closing(db.connect(p)) as conn:
        assert db.employee(conn, "e_manager")["name"] == "B Boss"
