from contextlib import closing

from fastapi import APIRouter

from api import cases, db, models, samples
from api import ledger as L
from api.samples import stub

router = APIRouter()


@router.get("/ledger", response_model=models.LedgerOut)
def ledger(company: str | None = None, verdict: str | None = None, limit: int = 200, offset: int = 0):
    with closing(db.connect()) as conn:
        txns, total = L.rows(conn, company, verdict, limit, offset, cases.POLICY.version)
    return {"transactions": txns, "total": total}


@router.post("/ledger/audit", response_model=models.AuditSummary)
def audit(req: models.AuditRequest):
    with closing(db.connect()) as conn:
        return L.audit(conn, req.company, cases.POLICY, cases.POLICY.by_id)


@router.post("/data/reload", response_model=models.ReloadOut)
def reload_data():
    return stub(samples.SAMPLE_RELOAD)
