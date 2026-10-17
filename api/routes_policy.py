from fastapi import APIRouter

from api import models, samples
from api.samples import stub

router = APIRouter()


@router.get("/policy", response_model=models.PolicyOut)
def policy():
    return stub(samples.SAMPLE_POLICY)


@router.post("/policy/audit", response_model=models.PolicyAudit)
def policy_audit():
    return stub(samples.SAMPLE_POLICY_AUDIT)
