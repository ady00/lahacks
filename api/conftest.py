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
