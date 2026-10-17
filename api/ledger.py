"""Ledger: every transaction decided by the engine, verdicts cached per (txn_id, policy_version)."""
import json
import time

from api import cases, db

_FROM = "FROM transactions t JOIN verdicts v ON v.txn_id = t.txn_id AND v.policy_version = ?"


def row_case(conn, txn: dict, policy_version: str) -> dict:
    """Cached verdict for this policy version, else decide once and cache it."""
    if (hit := db.get_verdict(conn, txn["txn_id"], policy_version)):
        return hit["case"]
    try:
        case = cases.decide_transaction(
            txn, json.loads(txn["extraction_json"]) if txn.get("extraction_json") else None,
            db.txn_pre_approved(conn, txn["txn_id"]), db.employee(conn, txn["employee_id"]))
    except Exception as e:  # ponytail: never let one bad row kill the audit
        case = {"case_id": "", "created_at": txn.get("timestamp") or "", "employee_id": txn.get("employee_id") or "",
                "text": txn.get("memo") or "", "policy_version": policy_version, "verdict": "undetermined",
                "facts": {}, "violations": [], "applied": [], "fix": None, "questions": [],
                "explanation": f"Could not evaluate: {e}", "awaiting_approval": False,
                "approval": None, "authorization": None}
    db.put_verdict(conn, txn["txn_id"], policy_version, case)
    return case


def _ensure(conn, company, policy_version):
    """Decide every in-scope transaction that has no verdict for this policy version yet."""
    sql = "SELECT t.* FROM transactions t LEFT JOIN verdicts v ON v.txn_id = t.txn_id AND v.policy_version = ? " \
          "WHERE v.txn_id IS NULL" + (" AND t.company = ?" if company else "")
    for r in conn.execute(sql, (policy_version, *([company] if company else []))).fetchall():
        row_case(conn, dict(r), policy_version)


def _scope(company, verdict):
    where, args = "", []
    for col, val in (("t.company", company), ("v.verdict", verdict)):
        if val:
            where, args = where + f" AND {col} = ?", args + [val]
    return where, args


def _row(r) -> dict:
    case = json.loads(r["case_json"])
    return {**{k: r[k] if r[k] is not None else "" for k in
               ("txn_id", "company", "employee_id", "vendor", "memo", "amount", "timestamp", "qb_category", "coded_account")},
            "verdict": r["verdict"], "violations": [v["rule"] for v in case["violations"]], "case": case}


def rows(conn, company, verdict, limit, offset, policy_version) -> tuple[list[dict], int]:
    _ensure(conn, company, policy_version)
    where, args = _scope(company, verdict)
    total = conn.execute(f"SELECT COUNT(*) {_FROM} WHERE 1=1{where}", (policy_version, *args)).fetchone()[0]
    cur = conn.execute(f"SELECT t.*, v.verdict, v.case_json {_FROM} WHERE 1=1{where} ORDER BY t.rowid LIMIT ? OFFSET ?",
                       (policy_version, *args, limit, offset))
    return [_row(r) for r in cur], total


def audit(conn, company, policy, by_id) -> dict:
    t0 = time.perf_counter()
    pv = policy.version
    _ensure(conn, company, pv)
    where, args = _scope(company, None)
    counts = dict(conn.execute(f"SELECT v.verdict, COUNT(*) {_FROM} WHERE 1=1{where} GROUP BY v.verdict", (pv, *args)).fetchall())
    by_verdict = {k: counts.get(k, 0) for k in ("compliant", "violation", "undetermined")}
    rule_n, top = {}, []
    where, args = _scope(company, "violation")
    for r in conn.execute(f"SELECT t.*, v.verdict, v.case_json {_FROM} WHERE 1=1{where} ORDER BY t.rowid", (pv, *args)):
        row = _row(r)
        if len(top) < 20:
            top.append(row)
        for rid in set(row["violations"]):
            rule_n[rid] = rule_n.get(rid, 0) + 1
    by_rule = [{"rule": rid, "text": by_id[rid].text if rid in by_id else "", "count": n}
               for rid, n in sorted(rule_n.items(), key=lambda kv: (-kv[1], kv[0]))]
    return {"company": company, "policy_version": pv, "n": sum(by_verdict.values()), "by_verdict": by_verdict,
            "by_rule": by_rule, "top_violations": top, "elapsed_ms": int((time.perf_counter() - t0) * 1000)}
