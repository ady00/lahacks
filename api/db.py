"""SQLite storage (stdlib only). One connection per request: `with closing(db.connect()) as conn:`."""
import csv
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases(case_id TEXT PRIMARY KEY, created_at TEXT, employee_id TEXT, text TEXT, amount REAL,
  timestamp TEXT, answers_json TEXT, case_json TEXT, policy_version TEXT, awaiting_approval INTEGER);
CREATE TABLE IF NOT EXISTS transactions(txn_id TEXT PRIMARY KEY, company TEXT, employee_id TEXT, vendor TEXT, memo TEXT,
  amount REAL, timestamp TEXT, qb_category TEXT, coded_account TEXT, receipt_attached INTEGER, receipt_date TEXT,
  source TEXT, extraction_json TEXT);
CREATE TABLE IF NOT EXISTS verdicts(txn_id TEXT, policy_version TEXT, verdict TEXT, case_json TEXT,
  PRIMARY KEY(txn_id, policy_version));
CREATE TABLE IF NOT EXISTS approvals(id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT, txn_id TEXT, approver TEXT,
  approved INTEGER, at TEXT);
CREATE TABLE IF NOT EXISTS policy_versions(version TEXT PRIMARY KEY, rules_json TEXT, loaded_at TEXT);
CREATE TABLE IF NOT EXISTS employees(employee_id TEXT PRIMARY KEY, name TEXT, role TEXT, manager_id TEXT);
"""
SEED_EMPLOYEES = [
    ("e_newhire", "Sam Lee", "employee", "e_manager"),
    ("e_intern", "Ria Patel", "intern", "e_manager"),
    ("e_contractor", "Jo Kim", "contractor", "e_manager"),
    ("e_manager", "Dana Ortiz", "employee", ""),
]
TXN_COLS = ["txn_id", "company", "employee_id", "vendor", "memo", "amount", "timestamp", "qb_category",
            "coded_account", "receipt_attached", "receipt_date", "source", "extraction_json"]


def connect(path=None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path or os.environ.get("POP_DB", "pop.db")))
    conn.row_factory = sqlite3.Row
    init(conn)
    return conn


def init(conn):
    conn.executescript(SCHEMA)
    if not conn.execute("SELECT 1 FROM employees LIMIT 1").fetchone():
        conn.executemany("INSERT INTO employees VALUES (?,?,?,?)", SEED_EMPLOYEES)
    conn.commit()


def _one(conn, sql, args=()):
    r = conn.execute(sql, args).fetchone()
    return dict(r) if r else None


# ---- cases ----
def put_case(conn, case: dict, answers: dict):
    amount = ((case.get("facts") or {}).get("amount") or {}).get("value")
    conn.execute(
        "INSERT INTO cases(case_id, created_at, employee_id, text, amount, timestamp, answers_json, case_json,"
        " policy_version, awaiting_approval) VALUES (?,?,?,?,?,?,?,?,?,?)"
        " ON CONFLICT(case_id) DO UPDATE SET amount=excluded.amount, timestamp=excluded.timestamp,"
        " answers_json=excluded.answers_json, case_json=excluded.case_json, policy_version=excluded.policy_version,"
        " awaiting_approval=excluded.awaiting_approval",
        (case["case_id"], case.get("created_at"), case.get("employee_id"), case.get("text"), amount,
         case.get("timestamp"), json.dumps(answers), json.dumps(case), case.get("policy_version"),
         int(bool(case.get("awaiting_approval")))))
    conn.commit()


def get_case(conn, case_id):
    r = conn.execute("SELECT case_json FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    return json.loads(r[0]) if r else None


def get_answers(conn, case_id) -> dict:
    r = conn.execute("SELECT answers_json FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    return json.loads(r[0]) if r and r[0] else {}


def list_cases(conn, awaiting_approval=None) -> list:
    sql, args = "SELECT case_json FROM cases", ()
    if awaiting_approval is not None:
        sql, args = sql + " WHERE awaiting_approval = ?", (int(awaiting_approval),)
    return [json.loads(r[0]) for r in conn.execute(sql + " ORDER BY created_at, rowid", args)]


# ---- approvals ----
def add_approval(conn, case_id, txn_id, approver, approved: bool, at):
    conn.execute("INSERT INTO approvals(case_id, txn_id, approver, approved, at) VALUES (?,?,?,?,?)",
                 (case_id, txn_id, approver, int(approved), at))
    conn.commit()


def case_approval(conn, case_id):
    return _one(conn, "SELECT * FROM approvals WHERE case_id = ? ORDER BY id DESC LIMIT 1", (case_id,))


def txn_pre_approved(conn, txn_id) -> bool:
    return conn.execute("SELECT 1 FROM approvals WHERE txn_id = ? AND approved = 1 LIMIT 1", (txn_id,)).fetchone() is not None


# ---- transactions ----
def upsert_transactions(conn, rows: list):
    sets = ", ".join(f"{c}=excluded.{c}" for c in TXN_COLS[1:])
    ins = (f"INSERT INTO transactions({', '.join(TXN_COLS)}) VALUES ({','.join('?' * len(TXN_COLS))})"
           f" ON CONFLICT(txn_id) DO UPDATE SET {sets}")
    for row in rows:
        new = tuple(row.get(c) for c in TXN_COLS)  # missing keys -> NULL
        old = conn.execute(f"SELECT {', '.join(TXN_COLS)} FROM transactions WHERE txn_id = ?", (new[0],)).fetchone()
        if old is not None and tuple(old) != new:
            conn.execute("DELETE FROM verdicts WHERE txn_id = ?", (new[0],))  # changed row: re-decide
        conn.execute(ins, new)
    conn.commit()


def list_transactions(conn, company=None, limit=200, offset=0) -> list:
    where, args = ("WHERE company = ?", (company,)) if company else ("", ())
    return [dict(r) for r in conn.execute(f"SELECT * FROM transactions {where} ORDER BY rowid LIMIT ? OFFSET ?",
                                          (*args, limit, offset))]


def count_transactions(conn, company=None) -> int:
    where, args = ("WHERE company = ?", (company,)) if company else ("", ())
    return conn.execute(f"SELECT COUNT(*) FROM transactions {where}", args).fetchone()[0]


# ---- verdicts / employees / policy ----
def get_verdict(conn, txn_id, policy_version):
    r = conn.execute("SELECT verdict, case_json FROM verdicts WHERE txn_id = ? AND policy_version = ?",
                     (txn_id, policy_version)).fetchone()
    return {"txn_id": txn_id, "policy_version": policy_version, "verdict": r[0], "case": json.loads(r[1])} if r else None


def put_verdict(conn, txn_id, policy_version, case: dict):
    conn.execute("INSERT OR REPLACE INTO verdicts VALUES (?,?,?,?)",
                 (txn_id, policy_version, case["verdict"], json.dumps(case)))
    conn.commit()


def employee(conn, employee_id):
    return _one(conn, "SELECT * FROM employees WHERE employee_id = ?", (employee_id,))


def record_policy(conn, version, rules):
    conn.execute("INSERT OR IGNORE INTO policy_versions VALUES (?,?,datetime('now'))", (version, json.dumps(rules)))
    conn.commit()


# ---- Person B's data files ----
def _csv(path: Path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        yield from csv.DictReader(f)


def load_data_dir(conn, data_dir=None) -> dict:
    """Load B's files; never raises on a bad row. Returns counts plus a reason for every skipped transactions row."""
    d = Path(data_dir or os.environ.get("POP_DATA_DIR", "data"))
    out = {"transactions": 0, "employees": 0, "extractions": 0, "approvals": 0, "skipped": []}
    if (p := d / "employees.csv").exists():
        emps = [(r["employee_id"], r.get("name") or "", r.get("role") or "", r.get("manager_id") or "")
                for r in _csv(p) if r.get("employee_id")]
        conn.executemany("INSERT OR REPLACE INTO employees VALUES (?,?,?,?)", emps)
        out["employees"] = len(emps)
    if (p := d / "approvals.csv").exists():
        conn.execute("DELETE FROM approvals WHERE case_id IS NULL")  # file rows only; /approve rows survive
        apps = [(r["txn_id"], r.get("approver"), r.get("approved_at")) for r in _csv(p) if r.get("txn_id")]
        conn.executemany("INSERT INTO approvals(case_id, txn_id, approver, approved, at) VALUES (NULL,?,?,1,?)", apps)
        out["approvals"] = len(apps)
    ext = {}
    if (p := d / "extractions.jsonl").exists():
        for line in p.read_text(encoding="utf-8-sig").splitlines():
            try:
                o = json.loads(line)
                ext[o["txn_id"]] = json.dumps(o["facts"], sort_keys=True)
            except (ValueError, KeyError, TypeError):  # blank line, bad JSON, no txn_id/facts: skip
                pass
        out["extractions"] = len(ext)
    rows, seen, owner = [], set(), {}
    if (p := d / "transactions.csv").exists():
        for r in _csv(p):
            tid = (r.get("txn_id") or "").strip()
            r["txn_id"] = tid
            seen.add(tid)
            try:
                amount = float(r.get("amount"))
            except (TypeError, ValueError):
                amount = 0
            if not tid:
                reason = "missing txn_id"
            elif not amount > 0:  # also NaN
                reason = "amount must be > 0 (refunds and credits are not audited)"
            else:
                try:
                    datetime.fromisoformat((r.get("timestamp") or "").strip())
                    reason = None
                except ValueError:
                    reason = "bad timestamp"
            if reason is None:
                if tid not in owner:
                    old = conn.execute("SELECT company FROM transactions WHERE txn_id = ?", (tid,)).fetchone()
                    owner[tid] = old[0] if old else r.get("company")
                if owner[tid] != r.get("company"):
                    reason = "txn_id collision"
            if reason:
                out["skipped"].append({"txn_id": tid, "reason": reason})
                continue
            r["amount"] = amount
            ra = (r.get("receipt_attached") or "").strip().lower()  # blank or unrecognized = unknown, never 0
            r["receipt_attached"] = 1 if ra in ("1", "1.0", "true", "yes") else 0 if ra in ("0", "0.0", "false", "no") else None
            r["employee_id"] = r.get("employee_id") or None
            rows.append(r)
    for r in rows:  # no extraction in the file this time: keep the stored one so a reload doesn't churn verdicts
        r["extraction_json"] = ext.get(r["txn_id"]) or (conn.execute(
            "SELECT extraction_json FROM transactions WHERE txn_id = ?", (r["txn_id"],)).fetchone() or [None])[0]
    for txn_id, facts in ext.items():  # extraction for a row already in the db
        if txn_id not in seen and (old := _one(conn, "SELECT * FROM transactions WHERE txn_id = ?", (txn_id,))):
            rows.append(dict(old, extraction_json=facts))
    upsert_transactions(conn, rows)
    out["transactions"] = len({r["txn_id"] for r in rows if r["txn_id"] in seen})
    conn.commit()
    return out
