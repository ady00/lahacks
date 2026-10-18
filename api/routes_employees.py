import secrets
from contextlib import closing
from datetime import date

from fastapi import APIRouter, HTTPException

from api import cases, db, models

router = APIRouter()


@router.post("/employees", response_model=models.Employee)
def signup(req: models.EmployeeIn):
    row = req.model_dump()
    row["employee_id"] = "e_" + secrets.token_hex(4)
    try:
        row["start_date"] = date.fromisoformat(row["start_date"]).isoformat() if row["start_date"] else cases.now_la().date().isoformat()
    except ValueError:
        raise HTTPException(422, "start_date must be YYYY-MM-DD")
    with closing(db.connect()) as conn:
        db.add_employee(conn, row)
        return db.employee(conn, row["employee_id"])


@router.get("/employees", response_model=models.EmployeeList)
def list_employees():
    with closing(db.connect()) as conn:
        return {"employees": db.list_employees(conn)}


@router.get("/employees/{employee_id}/rules", response_model=models.ApplicableOut)
def applicable_rules(employee_id: str):
    """What applies to you: every rule, proven against this person's role and tenure, with days left on probation rules."""
    with closing(db.connect()) as conn:
        e = db.employee(conn, employee_id)
    if e is None:
        raise HTTPException(404, "unknown employee")
    facts = cases.standing_facts(e)
    return {"employee": e, "facts": facts, "rules": cases.POLICY.applicable(facts)}
