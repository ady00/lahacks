import os

import httpx
import pytest

from api import jev_live

OK = {"model": "jev-1.13.0", "usage": {"input_tokens": 1, "output_tokens": 2}, "answers": {
    "expense_kind": {"type": "choice", "choice": "meal", "confidence": 0.97, "probabilities": {"meal": 0.97}},
    "client_present": {"type": "noul", "noul": 0.91},
    "at_company_event": {"type": "noul", "noul": 0.08}}}


def _post(monkeypatch, status=200, body=OK):
    monkeypatch.setenv("TYPESAFE_API_KEY", "k")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: httpx.Response(status, json=body, request=httpx.Request("POST", "http://x")))


def test_shape(monkeypatch):
    _post(monkeypatch)
    assert jev_live.extract("dinner") == {"expense_kind": {"value": "meal", "p": 0.97},
                                          "client_present": {"p": 0.91}, "at_company_event": {"p": 0.08}}
    _, meta = jev_live.extract_with_meta("dinner")
    assert meta["model"] == "jev-1.13.0" and meta["usage"]["output_tokens"] == 2 and meta["latency_ms"] >= 0


def test_unknown_choice_dropped(monkeypatch):
    body = {**OK, "answers": {**OK["answers"], "expense_kind": {"type": "choice", "choice": "yacht", "confidence": 1.0}}}
    _post(monkeypatch, body=body)
    assert "expense_kind" not in jev_live.extract("x")


def test_missing_key(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="TYPESAFE_API_KEY not set"):
        jev_live.extract("x")


def test_http_500(monkeypatch):
    _post(monkeypatch, 500, {"error": "boom"})
    with pytest.raises(jev_live.JevError):
        jev_live.extract("x")


def test_bad_shape(monkeypatch):
    _post(monkeypatch, body={"answers": {}})
    with pytest.raises(jev_live.JevError):
        jev_live.extract("x")


@pytest.mark.skipif(os.environ.get("POP_LIVE_JEV") != "1", reason="set POP_LIVE_JEV=1 (needs TYPESAFE_API_KEY)")
def test_live():
    out = jev_live.extract("Client dinner with Acme's CFO, about $48")
    assert out["expense_kind"]["value"] == "meal" and out["client_present"]["p"] > 0.5
