import json

from api import models, routes_eval, samples


def test_eval_serves_results_file(client, tmp_path, monkeypatch):
    monkeypatch.setattr(routes_eval, "EVAL_RESULTS", tmp_path / "results.json")
    r = client.get("/eval")
    assert r.headers.get("x-stub") == "1" and r.json() == {"as_of": None, "n_heldout": 0, "systems": []}
    (tmp_path / "results.json").write_text(json.dumps(samples.SAMPLE_EVAL))
    r = client.get("/eval")
    assert r.headers.get("x-stub") is None and r.json()["systems"][0]["name"]
    models.EvalOut.model_validate(r.json())


def test_eval_bad_file_falls_back_to_empty_stub(client, tmp_path, monkeypatch):
    p = tmp_path / "results.json"
    monkeypatch.setattr(routes_eval, "EVAL_RESULTS", p)
    for bad in ("not json", json.dumps({"as_of": None})):
        p.write_text(bad)
        r = client.get("/eval")
        assert r.status_code == 200 and r.headers.get("x-stub") == "1" and r.json()["systems"] == []


def test_health_policy_version_and_stub_flag(client, tmp_path, monkeypatch):
    import re
    from pathlib import Path

    import engine
    from engine.rules import load_policy

    d = Path(engine.__file__).parent
    want = load_policy(d / "demo_policy.json", d / "irs_pack.json").version
    monkeypatch.setattr(routes_eval, "EVAL_RESULTS", tmp_path / "results.json")
    r = client.get("/health")
    j = r.json()
    assert j["ok"] is True and re.fullmatch(r"[0-9a-f]{12}", j["policy_version"]) and j["policy_version"] == want
    assert j["stub"] is True and r.headers.get("x-stub") == "1"
    (tmp_path / "results.json").write_text(json.dumps(samples.SAMPLE_EVAL))
    r = client.get("/health")
    assert r.json()["stub"] is False and r.headers.get("x-stub") is None
    models.Health.model_validate(r.json())


def test_reviewer_health_cached_once_and_cwd_independent(client, tmp_path, monkeypatch):
    want = client.get("/health").json()["policy_version"]
    calls = []
    real = routes_eval.load_policy
    monkeypatch.setattr(routes_eval, "load_policy", lambda *p: calls.append(p) or real(*p))
    routes_eval._policy_version.cache_clear()
    monkeypatch.chdir(tmp_path)
    vs = {client.get("/health").json()["policy_version"] for _ in range(3)}
    assert vs == {want} and len(calls) == 1


def test_reviewer_health_stub_flips_back_when_file_removed(client, tmp_path, monkeypatch):
    p = tmp_path / "results.json"
    monkeypatch.setattr(routes_eval, "EVAL_RESULTS", p)
    p.write_text("not json")  # exists-only check: invalid file still counts as present
    r = client.get("/health")
    assert r.json()["stub"] is False and "x-stub" not in r.headers
    p.unlink()
    r = client.get("/health")
    assert r.json()["stub"] is True and r.headers["x-stub"] == "1" and r.json()["policy_version"] != "stub00000000"


def test_reviewer_health_matches_policy_route_version(client):
    h = client.get("/health").json()["policy_version"]
    p = client.get("/policy")
    if "x-stub" not in p.headers:
        assert p.json()["version"] == h
