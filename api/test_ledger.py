import json

from api import cases, db


def _t(txn_id, amount=18.5, ext=None, **kw):
    return dict(txn_id=txn_id, company="demo", employee_id="e_newhire", vendor="V", memo="M", amount=amount,
                timestamp="2026-09-30T08:10:00-07:00", qb_category="Travel", receipt_attached=1,
                receipt_date="2026-10-01", source="intuit", extraction_json=json.dumps(ext) if ext else None, **kw)


def _seed(conn):
    db.upsert_transactions(conn, [
        _t("t1", ext={"expense_kind": {"value": "rideshare", "p": 0.95}}),
        dict(_t("t2", 120, {"expense_kind": {"value": "meal", "p": 0.96}, "client_present": {"p": 0.9},
                            "at_company_event": {"p": 0.05}}), vendor="Nobu", memo="NOBU LA",
             timestamp="2026-09-20T20:30:00-07:00", receipt_date="2026-09-21", source="injected"),
        _t("t3", 12)])


def test_ledger_audit_counts_and_caches(client):
    conn = db.connect()
    _seed(conn)
    a = client.post("/ledger/audit", json={"company": "demo"}).json()
    assert a["n"] == 3 and a["by_verdict"] == {"compliant": 1, "violation": 0, "undetermined": 2}
    assert {r["rule"] for r in a["by_rule"]} == {"IRS-meal"}  # the miscoded Nobu dinner: an IRS note counted in the audit
    assert conn.execute("select count(*) from verdicts").fetchone()[0] == 3
    r = client.get("/ledger", params={"company": "demo", "verdict": "undetermined"})
    assert "x-stub" not in r.headers and r.json()["total"] == 2
    t2 = next(t for t in r.json()["transactions"] if t["txn_id"] == "t2")
    assert t2["violations"] == [] and t2["notes"] == ["IRS-meal"]
    assert [t["txn_id"] for t in client.get("/ledger").json()["transactions"]] == ["t3", "t1", "t2"]  # newest first


def test_answer_redecides_one_row(client):
    _seed(db.connect())
    client.post("/ledger/audit", json={"company": "demo"})
    q = next(t for t in client.get("/ledger").json()["transactions"] if t["verdict"] == "undetermined")
    fact, opts = q["case"]["questions"][0]["fact"], q["case"]["questions"][0]["options"]
    val = opts[0] if opts else True
    assert client.post(f"/ledger/{q['txn_id']}/answer", json={"fact": "nope", "value": True}).status_code == 422
    assert client.post("/ledger/missing/answer", json={"fact": fact, "value": True}).status_code in (404, 422)
    r = client.post(f"/ledger/{q['txn_id']}/answer", json={"fact": fact, "value": val}).json()
    assert r["case"]["facts"][fact]["value"] == val and r["case"]["facts"][fact]["source"] == "user" and fact not in [x["fact"] for x in r["case"]["questions"]]


def test_cache_and_changed_row_redecided_alone(client, monkeypatch):
    conn = db.connect()
    _seed(conn)
    calls = []
    real = cases.decide_transaction
    monkeypatch.setattr(cases, "decide_transaction", lambda txn, *a: calls.append(txn["txn_id"]) or real(txn, *a))
    client.post("/ledger/audit", json={"company": "demo"})
    assert sorted(calls) == ["t1", "t2", "t3"]
    calls.clear()
    client.post("/ledger/audit", json={"company": "demo"})
    client.get("/ledger")
    assert calls == []
    db.upsert_transactions(conn, [_t("t3", 99)])  # new amount: db drops its verdicts
    client.post("/ledger/audit", json={"company": "demo"})
    assert calls == ["t3"]


def test_one_bad_row_does_not_abort(client, monkeypatch):
    _seed(db.connect())
    real = cases.decide_transaction

    def boom(txn, *a):
        if txn["txn_id"] == "t1":
            raise ValueError("bad row")
        return real(txn, *a)
    monkeypatch.setattr(cases, "decide_transaction", boom)
    a = client.post("/ledger/audit", json={"company": "demo"}).json()
    assert a["n"] == 3 and a["by_verdict"]["undetermined"] == 3
    row = next(r for r in client.get("/ledger", params={"verdict": "undetermined"}).json()["transactions"] if r["txn_id"] == "t1")
    assert row["case"]["explanation"] == "Could not evaluate: bad row"


def test_paging_company_filter_and_unknown_verdict(client):
    conn = db.connect()
    db.upsert_transactions(conn, [_t(f"d{i:02d}", 4000 + 500 * i) for i in range(12)] + [dict(_t("a1"), company="acme")])  # 9 are over $5,000
    full = client.get("/ledger").json()
    assert full["total"] == 13
    pages = [r["txn_id"] for o in range(0, 13, 5) for r in client.get("/ledger", params={"limit": 5, "offset": o}).json()["transactions"]]
    assert pages == [r["txn_id"] for r in full["transactions"]]
    assert client.get("/ledger", params={"company": "acme"}).json()["total"] == 1
    v = client.get("/ledger", params={"company": "demo", "verdict": "violation", "limit": 1}).json()
    assert v["total"] == sum(r["verdict"] == "violation" for r in full["transactions"] if r["company"] == "demo") > 1
    assert len(v["transactions"]) == 1
    assert client.get("/ledger", params={"verdict": "bogus"}).json() == {"transactions": [], "total": 0}


def test_unknown_facts_undetermined_unicode_and_repeat(client):
    conn = db.connect()
    mid = {"expense_kind": {"value": "meal", "p": 0.5}, "client_present": {"p": 0.5}, "at_company_event": {"p": 0.5}}
    db.upsert_transactions(conn, [dict(_t("u1", 20, mid), memo="CAFÉ ☕ 東京"), _t("u2", 20)])
    a = client.post("/ledger/audit", json={"company": "demo"}).json()
    assert a["by_verdict"] == {"compliant": 0, "violation": 0, "undetermined": 2} and a["n"] == 2
    assert client.post("/ledger/audit", json={"company": "demo"}).json()["by_verdict"] == a["by_verdict"]
    rows = client.get("/ledger").json()["transactions"]
    assert rows[-1]["memo"] == "CAFÉ ☕ 東京"  # same timestamp: later insert first and all(r["case"]["questions"] for r in rows)
    assert client.post("/ledger/audit", json={"company": "nobody"}).json()["by_verdict"] == {
        "compliant": 0, "violation": 0, "undetermined": 0}



def test_coded_account_comes_from_qb_category(client):
    db.upsert_transactions(db.connect(), [_t("c1")])  # CSV rows carry no coded_account column
    row = client.get("/ledger").json()["transactions"][0]
    assert row["coded_account"] == "travel" == row["case"]["facts"]["coded_account"]["value"]


HEADER = "txn_id,company,employee_id,vendor,memo,amount,timestamp,qb_category,receipt_attached,receipt_date,source\n"

def test_reload_skips_refunds_and_keeps_blank_receipt_unknown(client, tmp_path, monkeypatch):
    monkeypatch.setenv("POP_DATA_DIR", str(tmp_path)); conn = db.connect()
    (tmp_path / "transactions.csv").write_text(HEADER
        + "t1,demo,e_newhire,Uber,UBER TRIP,18.5,2026-09-30T08:10:00-07:00,Travel,,2026-10-01,intuit\n"
        + "t2,demo,e_newhire,Uber,UBER REFUND,-18.5,2026-10-02T08:10:00-07:00,Travel,1,,intuit\n")
    r = client.post("/data/reload").json()
    assert r["transactions"] == 1
    assert r["skipped"] == [{"txn_id": "t2", "reason": "amount must be > 0 (refunds and credits are not audited)"}]
    row = db.list_transactions(conn, company="demo")[0]
    assert row["receipt_attached"] is None
    assert "receipt_attached" not in cases.decide_transaction(row, None, False, db.employee(conn, "e_newhire"))["facts"]

def test_reload_then_audit_is_incremental(client, tmp_path, monkeypatch):
    monkeypatch.setenv("POP_DATA_DIR", str(tmp_path)); conn = db.connect()
    T1 = "t1,demo,e_newhire,Uber,UBER TRIP,18.5,2026-09-30T08:10:00-07:00,Travel,1,2026-10-01,intuit\n"
    (tmp_path / "transactions.csv").write_text(HEADER + T1)
    client.post("/data/reload"); client.post("/ledger/audit", json={"company": "demo"})
    first = conn.execute("select case_json from verdicts where txn_id='t1'").fetchone()[0]
    with open(tmp_path / "transactions.csv", "a") as f:
        f.write("t3,demo,e_newhire,Nobu,NOBU LA,7000,2026-09-20T20:30:00-07:00,Travel,1,2026-09-21,injected\n")
    assert client.post("/data/reload").json()["transactions"] == 2
    a = client.post("/ledger/audit", json={"company": "demo"}).json()
    assert a["n"] == 2 and conn.execute("select count(*) from verdicts").fetchone()[0] == 2
    assert conn.execute("select case_json from verdicts where txn_id='t1'").fetchone()[0] == first   # unchanged row, untouched verdict
    (tmp_path / "transactions.csv").write_text(HEADER + T1.replace("18.5", "6000"))                # changed row, verdict dropped
    client.post("/data/reload")
    assert conn.execute("select count(*) from verdicts where txn_id='t1'").fetchone()[0] == 0
    assert client.post("/ledger/audit", json={"company": "demo"}).json()["by_verdict"]["violation"] == 2   # both over the $5,000 line


def test_reload_during_audits_leaves_no_stale_verdicts(tmp_path):
    """Threads (reload with changed amounts vs audits) in a subprocess: Z3 from threads must not touch the pytest process."""
    import subprocess, sys, textwrap
    code = textwrap.dedent('''
        import os, sys, threading, json, time
        d = sys.argv[1]; os.environ["POP_DB"] = d + "/t.db"; os.environ["POP_DATA_DIR"] = d
        from fastapi.testclient import TestClient
        from api.main import app
        from api import db, cases
        H = "txn_id,company,employee_id,vendor,memo,amount,timestamp,qb_category,receipt_attached,receipt_date,source\\n"
        def write(a):
            open(d + "/transactions.csv", "w").write(H + "".join(
                f"t{i},demo,e_newhire,Uber,UBER,{a},2026-09-30T08:10:00-07:00,Travel,1,2026-10-01,intuit\\n" for i in range(400)))
        cases.extract = lambda text: {}
        write(20)
        with TestClient(app) as c:
            c.post("/data/reload")
            def audits():
                for _ in range(4): assert c.post("/ledger/audit", json={"company": "demo"}).status_code == 200
            def reloads():
                for a in (95, 20, 95):
                    write(a); assert c.post("/data/reload").status_code == 200; time.sleep(0.05)
            ts = [threading.Thread(target=audits) for _ in range(3)] + [threading.Thread(target=reloads)]
            [t.start() for t in ts]; [t.join() for t in ts]
            c.post("/ledger/audit", json={"company": "demo"})
        conn = db.connect()
        rows = {r["txn_id"]: r["amount"] for r in db.list_transactions(conn, limit=1000)}
        bad = [t for t, cj in conn.execute("select txn_id, case_json from verdicts")
               if json.loads(cj)["facts"]["amount"]["value"] != rows[t]]
        assert not bad, len(bad)
    ''')
    r = subprocess.run([sys.executable, "-c", code, str(tmp_path)], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-2000:]
