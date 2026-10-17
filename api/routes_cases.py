from contextlib import closing

from fastapi import APIRouter

from api import cases, db, models

router = APIRouter()


@router.post("/check", response_model=models.Case)
def check(req: models.CheckRequest):
    with closing(db.connect()) as conn:
        return cases.new_case(conn, req)


@router.get("/cases", response_model=models.CaseList)
def list_cases(awaiting_approval: bool | None = None):
    with closing(db.connect()) as conn:
        return {"cases": db.list_cases(conn, awaiting_approval)}


@router.get("/cases/{case_id}", response_model=models.Case)
def get_case(case_id: str):
    with closing(db.connect()) as conn:
        return cases._get(conn, case_id)


@router.post("/cases/{case_id}/answer", response_model=models.Case)
def answer(case_id: str, req: models.AnswerRequest):
    with closing(db.connect()) as conn:
        return cases.answer(conn, case_id, req.fact, req.value)


@router.post("/cases/{case_id}/approve", response_model=models.Case)
def approve(case_id: str, req: models.ApproveRequest):
    with closing(db.connect()) as conn:
        return cases.approve(conn, case_id, req.approver, req.approved)


@router.post("/cases/{case_id}/authorize", response_model=models.Authorization)
def authorize(case_id: str):
    with closing(db.connect()) as conn:
        return cases.authorize(conn, case_id)
