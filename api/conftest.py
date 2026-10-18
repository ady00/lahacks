# shared by every api/test_*.py; Task 8 adds the extractor and DB fixtures here
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("POP_DB", str(tmp_path / "t.db"))          # read at call time by db.connect (Task 6)
    monkeypatch.setenv("POP_DATA_DIR", str(tmp_path / "nodata"))  # no B files: the employee seed applies
    from api.main import app
    with TestClient(app) as c:   # the context manager is what runs startup; a bare TestClient(app) never does
        yield c


@pytest.fixture(autouse=True)
def fake_extractor(monkeypatch):
    # the demo dinner's Jev output; no test ever calls a live model
    from api import cases
    from api.jev_live import QUESTIONS
    quiet = {n: {"p": 0.05} for n, q in QUESTIONS.items() if q["type"] == "noul"}  # every other yes/no reads as no
    monkeypatch.setattr(cases, "extract", lambda text: {**quiet, "expense_kind": {"value": "meal", "p": 0.97},
        "client_present": {"p": 0.91}, "at_company_event": {"p": 0.08}, "traveling": {"p": 0.08}, "government_present": {"p": 0.05}})
    from api import infer
    monkeypatch.setattr(infer, "infer", lambda text: {})  # no test shells out to the claude CLI


@pytest.fixture(scope="package", autouse=True)
def drop_dotenv_after_api_tests():
    # api.main loads .env into os.environ; take it back out so tests/ (Person B) never see a live TYPESAFE_API_KEY
    yield
    import os, sys
    for k in getattr(sys.modules.get("api.main"), "DOTENV_KEYS", ()):
        os.environ.pop(k, None)
