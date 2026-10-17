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
    assert a["n"] == 3 and a["by_verdict"] == {"compliant": 1, "violation": 1, "undetermined": 1}
    assert {r["rule"] for r in a["by_rule"]} == {"3.4", "IRS-meal"}
    assert conn.execute("select count(*) from verdicts").fetchone()[0] == 3
    r = client.get("/ledger", params={"company": "demo", "verdict": "violation"})
    assert "x-stub" not in r.headers and r.json()["total"] == 1 and r.json()["transactions"][0]["txn_id"] == "t2"
    assert client.get("/ledger", params={"limit": 1, "offset": 1}).json()["transactions"][0]["txn_id"] == "t2"


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
    assert a["n"] == 3 and a["by_verdict"]["undetermined"] == 2
    row = client.get("/ledger", params={"verdict": "undetermined"}).json()["transactions"][0]
    assert row["case"]["explanation"] == "Could not evaluate: bad row"


def test_paging_company_filter_and_unknown_verdict(client):
    conn = db.connect()
    db.upsert_transactions(conn, [_t(f"d{i:02d}", 20 + 3 * i) for i in range(12)] + [dict(_t("a1"), company="acme")])
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
    assert rows[0]["memo"] == "CAFÉ ☕ 東京" and all(r["case"]["questions"] for r in rows)
    assert client.post("/ledger/audit", json={"company": "nobody"}).json()["by_verdict"] == {
        "compliant": 0, "violation": 0, "undetermined": 0}

