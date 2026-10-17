from fastapi import APIRouter

from api import models
from engine.bank_rules import check_bank_rules as _check

router = APIRouter()


@router.post("/bank-rules/check", response_model=models.BankRulesOut)
def check_bank_rules(body: models.BankRulesRequest):
    return models.BankRulesOut.model_validate(_check([r.model_dump() for r in body.rules]))
