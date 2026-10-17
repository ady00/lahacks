from pathlib import Path

import engine
from api.explain import explain, fix_phrase, phrase, question
from engine.rules import Decision, FixStep, Verdict, load_policy

_E = Path(engine.__file__).parent
P = load_policy(_E / "demo_policy.json", _E / "irs_pack.json")
DINNER = dict(role="employee", expense_kind="meal", client_present=True, at_company_event=False,
              amount=48, hour=19, days_since_purchase=0, pre_approved=False, coded_account="travel")
UNCODED = {k: v for k, v in DINNER.items() if k != "coded_account"}


def test_dinner_explanation_is_templated():
    d = P.decide(UNCODED, {})
    assert explain(d, P.by_id, []) == ("Any expense over $35 needs manager pre-approval (rule 3.4): amount $48, no pre-approval. "
                                       "Fix: get manager pre-approval. Post it as meals_50 (IRS-meal).")


def test_question_for_enum_carries_options():
    assert question("expense_kind", None)["options"][0] == "meal"
    assert question("receipt_attached", 0.5) == {"fact": "receipt_attached", "text": "Do you have the receipt?", "p": 0.5, "options": None}
    assert question("hour", None)["text"] == "What is hour?"


def test_compliant_explanation():
    d = P.decide({**UNCODED, "amount": 20}, {})
    assert d.verdict.status == "compliant"
    assert explain(d, P.by_id, []).startswith("Compliant: rules ") and " hold." in explain(d, P.by_id, [])


def test_undetermined_names_the_question():
    d = P.decide({k: v for k, v in UNCODED.items() if k != "pre_approved"}, {})
    assert d.verdict.status == "undetermined" and d.questions
    assert explain(d, P.by_id, []).startswith("Depends on: ")
    bare = Decision({}, {}, Verdict("undetermined", [], []), [], [])
    assert explain(bare, P.by_id, []) == "Depends on: a fact we don't know yet."
    assert explain(bare, P.by_id, ["amount"]) == "Depends on: What is the amount in dollars?"


def test_violation_without_fix():
    d = P.decide(UNCODED, {})
    d = d._replace(fix=None, derived={})
    assert explain(d, P.by_id, []).endswith("No change you control makes this compliant.")


def test_phrases():
    assert phrase("amount", 48) == "amount $48" and phrase("amount", 48.0) == "amount $48"
    assert phrase("amount", 48.5) == "amount $48.50"
    assert phrase("hour", 19) == "at 19:00" and phrase("mystery", [1]) == "mystery [1]"
    assert fix_phrase(FixStep("amount", 150, 100)) == "keep it at or under $100"
    assert fix_phrase(FixStep("amount", 150, 74.99)) == "keep it at or under $74.99"
    assert fix_phrase(FixStep("receipt_attached", None, False)) == "set receipt_attached to False"
