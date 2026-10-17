import threading
from contextlib import closing

from fastapi import APIRouter

from api import cases, db, models
from api import ledger as L

router = APIRouter()
_LOCK = threading.Lock()  # ponytail: one global ledger lock; per-company locks if audits ever need to overlap


@router.get("/ledger", response_model=models.LedgerOut)
def ledger(company: str | None = None, verdict: str | None = None, limit: int = 200, offset: int = 0):
    with _LOCK, closing(db.connect()) as conn:
        txns, total = L.rows(conn, company, verdict, limit, offset, cases.POLICY.version)
    return {"transactions": txns, "total": total}


@router.post("/ledger/audit", response_model=models.AuditSummary)
def audit(req: models.AuditRequest):
    with _LOCK, closing(db.connect()) as conn:
        return L.audit(conn, req.company, cases.POLICY, cases.POLICY.by_id)


@router.post("/data/reload", response_model=models.ReloadOut)
def reload_data():
    with _LOCK, closing(db.connect()) as conn:
        return db.load_data_dir(conn)
