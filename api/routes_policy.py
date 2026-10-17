from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter

import engine
from api import models
from engine.rules import load_policy

router = APIRouter()


@lru_cache(maxsize=1)
def _policy():
    d = Path(engine.__file__).parent
    return load_policy(d / "demo_policy.json", d / "irs_pack.json")


@router.get("/policy", response_model=models.PolicyOut)
def policy():
    from engine.schema import FACTS
    P = _policy()
    return {"version": P.version, "rules": [r.raw for r in P.rules],
            "facts": {n: s._asdict() for n, s in FACTS.items()}}


@router.post("/policy/audit", response_model=models.PolicyAudit)
def policy_audit():
    return _policy().audit()
