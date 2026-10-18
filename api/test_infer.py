import subprocess
from types import SimpleNamespace

from api import cases, infer
from api.infer import infer as real_infer  # bound before conftest's autouse patch stubs infer.infer


def test_parse_keeps_only_valid_answers():
    got = infer.parse({"expense_kind": "equipment", "amount": 200, "client_present": False, "traveling": None,
                       "bogus": 1, "at_company_event": "maybe"})
    assert got == {"expense_kind": {"value": "equipment", "p": 0.95, "source": "claude"},
                   "amount": {"value": 200.0, "source": "claude"},
                   "client_present": {"p": 0.05, "source": "claude"}}


def test_infer_reads_fenced_json(monkeypatch):
    monkeypatch.setenv("PATH", "/nonexistent")
    assert real_infer("x") == {}  # no CLI: silent {}
    monkeypatch.setattr(infer.shutil, "which", lambda _: "/bin/claude")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: SimpleNamespace(stdout='```json\n{"expense_kind": "equipment"}\n```'))
    assert real_infer("airpod")["expense_kind"]["value"] == "equipment"


def test_check_uses_claude_for_what_the_extractor_left_open(client, monkeypatch):
    monkeypatch.setattr(cases, "extract", lambda t: {"expense_kind": {"value": "other", "p": 0.5}})
    monkeypatch.setattr(infer, "infer", lambda t: infer.parse({"expense_kind": "equipment", "amount": 200, "traveling": False}))
    off = client.post("/check", json={"text": "cna i buy airpod 200 dollar", "employee_id": "e_newhire"}).json()
    assert "expense_kind" not in off["facts"] and off["verdict"] == "undetermined"  # default: no inference
    c = client.post("/check", json={"text": "cna i buy airpod, around two hundred", "employee_id": "e_newhire", "infer": True}).json()
    assert c["facts"]["expense_kind"] == {"value": "equipment", "source": "claude", "p": 0.95}
    assert c["facts"]["amount"] == {"value": 200.0, "source": "claude", "p": None}
    assert c["verdict"] != "undetermined" or "expense_kind" not in c["questions"]
