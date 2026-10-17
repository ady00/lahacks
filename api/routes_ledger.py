from fastapi import APIRouter

from api import models, samples
from api.samples import stub

router = APIRouter()


@router.get("/ledger", response_model=models.LedgerOut)
def ledger(company: str | None = None, verdict: str | None = None, limit: int = 200, offset: int = 0):
    return stub({"transactions": [samples.SAMPLE_LEDGER_ROW], "total": 1})


@router.post("/ledger/audit", response_model=models.AuditSummary)
def audit(req: models.AuditRequest):
    return stub(samples.SAMPLE_AUDIT)


@router.post("/data/reload", response_model=models.ReloadOut)
def reload_data():
    return stub(samples.SAMPLE_RELOAD)
