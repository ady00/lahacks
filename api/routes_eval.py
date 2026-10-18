import logging
from pathlib import Path

from fastapi import APIRouter

from api import models, samples
from api.samples import stub

log = logging.getLogger(__name__)
router = APIRouter()

EVAL_RESULTS = Path(__file__).resolve().parent.parent / "eval" / "results.json"  # tests monkeypatch this
_EMPTY = {"as_of": None, "n_heldout": 0, "systems": []}


@router.get("/eval", response_model=models.EvalOut)
def eval_table():
    try:
        return models.EvalOut.model_validate_json(EVAL_RESULTS.read_text())
    except FileNotFoundError:
        pass
    except Exception:  # unreadable or invalid file: serve the empty stub, never a 500
        log.exception("bad eval results file %s", EVAL_RESULTS)
    return stub(_EMPTY)


def _policy_version() -> str:
    from api import cases  # the live policy: rules added on the dashboard swap it at runtime
    return cases.POLICY.version


@router.get("/health", response_model=models.Health)
def health():
    out = {"ok": True, "policy_version": _policy_version(), "stub": not EVAL_RESULTS.exists()}
    return stub(out) if out["stub"] else out
