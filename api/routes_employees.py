import secrets
from contextlib import closing

from fastapi import APIRouter

from api import db, models

router = APIRouter()


@router.post("/employees", response_model=models.Employee)
def signup(req: models.EmployeeIn):
    employee_id = "e_" + secrets.token_hex(4)
    with closing(db.connect()) as conn:
        db.add_employee(conn, employee_id, req.name, req.role, req.manager_id)
        return db.employee(conn, employee_id)


@router.get("/employees", response_model=models.EmployeeList)
def list_employees():
    with closing(db.connect()) as conn:
        return {"employees": db.list_employees(conn)}
