from fastapi import APIRouter

from api import models, samples
from api.samples import stub

router = APIRouter()


@router.post("/check", response_model=models.Case)
def check(req: models.CheckRequest):
    return stub(samples.SAMPLE_CASE)


@router.get("/cases", response_model=models.CaseList)
def list_cases(awaiting_approval: bool | None = None):
    return stub({"cases": [samples.SAMPLE_CASE]})


@router.get("/cases/{case_id}", response_model=models.Case)
def get_case(case_id: str):
    return stub(samples.SAMPLE_CASE)


@router.post("/cases/{case_id}/answer", response_model=models.Case)
def answer(case_id: str, req: models.AnswerRequest):
    return stub(samples.SAMPLE_CASE)


@router.post("/cases/{case_id}/approve", response_model=models.Case)
def approve(case_id: str, req: models.ApproveRequest):
    return stub(samples.SAMPLE_CASE)


@router.post("/cases/{case_id}/authorize", response_model=models.Authorization)
def authorize(case_id: str):
    return stub(samples.SAMPLE_AUTH)
