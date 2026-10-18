import pytest

from api import try_text
from engine.rules import load_policy


@pytest.mark.parametrize("text,want", [
    ("$48", 48.0), ("$48.50", 48.5), ("MacBook, $1,299.00", 1299.0), ("$12,500", 12500.0),
    ("about $ 60", 60.0), ("no price", None), ("$0", None)])
def test_parse_amount(text, want):
    assert try_text.parse_amount(text) == want


def test_question_and_explanation_name_same_fact():
    P = load_policy(try_text.ENGINE / "demo_policy.json", try_text.ENGINE / "irs_pack.json")
    r = try_text.run(P, "Team dinner tonight", "e_newhire", None, "2026-10-17T12:00:00-07:00", True)  # noon: rules 6.1/6.2 must not fire
    assert r["verdict"] == "undetermined" and r["questions"][0]["fact"] == "amount"
    assert r["questions"][0]["text"] in r["explanation"]
