"""Sample JSON for every route, copied from API_CONTRACT.md. Stub responses carry X-Stub: 1."""
import copy

from fastapi.responses import JSONResponse

STUB_VERSION = "stub00000000"


def stub(payload: dict) -> JSONResponse:
    return JSONResponse(copy.deepcopy(payload), headers={"X-Stub": "1"})


SAMPLE_CASE = {
    "case_id": "c_8f2a1b3c",
    "created_at": "2026-10-17T19:30:00-07:00",
    "employee_id": "e_newhire",
    "text": "Client dinner Thursday with Acme's CFO, about $48.",
    "policy_version": STUB_VERSION,
    "verdict": "violation",
    "facts": {
        "role": {"value": "employee", "source": "employee", "p": None},
        "expense_kind": {"value": "meal", "source": "jev", "p": 0.97},
        "client_present": {"value": True, "source": "jev", "p": 0.91},
        "at_company_event": {"value": False, "source": "jev", "p": 0.08},
        "amount": {"value": 48, "source": "text", "p": None},
        "hour": {"value": 19, "source": "derived", "p": None},
        "days_since_purchase": {"value": 0, "source": "derived", "p": None},
        "pre_approved": {"value": False, "source": "approvals", "p": None},
        "coded_account": {"value": "meals_50", "source": "rules", "p": None},
    },
    "violations": [
        {
            "rule": "3.4",
            "layer": "company",
            "text": "Any expense over $35 needs manager pre-approval.",
            "because": ["amount", "pre_approved"],
        }
    ],
    "applied": [],
    "fix": [{"fact": "pre_approved", "from": False, "to": True}],
    "questions": [],
    "explanation": (
        "Any expense over $35 needs manager pre-approval (rule 3.4): amount $48, no pre-approval. "
        "Fix: get manager pre-approval. Post it as meals_50 (IRS-meal)."
    ),
    "awaiting_approval": True,
    "approval": None,
    "authorization": None,
}

SAMPLE_AUTH = {
    "auth_id": "auth_3c9d2e1f",
    "amount_limit": 48,
    "merchant_category": "5812 Eating places",
    "expires_at": "2026-10-18T19:30:00-07:00",
    "proof_hash": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
}

SAMPLE_LEDGER_ROW = {
    "txn_id": "t_000412",
    "company": "demo",
    "employee_id": "e_newhire",
    "vendor": "Nobu",
    "memo": "NOBU LA",
    "amount": 210,
    "timestamp": "2026-09-20T20:30:00-07:00",
    "qb_category": "Travel",
    "coded_account": "travel",
    "verdict": "violation",
    "violations": ["3.4", "IRS-meal"],
    "case": SAMPLE_CASE,
}

SAMPLE_AUDIT = {
    "company": "demo",
    "policy_version": STUB_VERSION,
    "n": 1240,
    "by_verdict": {"compliant": 1061, "violation": 142, "undetermined": 37},
    "by_rule": [{"rule": "3.4", "text": "Any expense over $35 needs manager pre-approval.", "count": 88}],
    "top_violations": [SAMPLE_LEDGER_ROW],
    "elapsed_ms": 1830,
}

SAMPLE_POLICY = {
    "version": STUB_VERSION,
    "rules": [
        {
            "id": "5.2",
            "layer": "company",
            "text": "Interns get no transport reimbursement except at company events.",
            "when": {"and": [{"eq": ["role", "intern"]}, {"in": ["expense_kind", ["rideshare", "airfare"]]}]},
            "require": "at_company_event",
        }
    ],
    "facts": {"role": {"kind": "enum", "values": ["employee", "contractor", "intern"], "mutable": False}},
}

SAMPLE_POLICY_AUDIT = {
    "dead": ["9.9"],
    "conflicts": [{"a": "5.2", "b": "6.1", "example": {"role": "intern", "expense_kind": "meal"}}],
}

SAMPLE_BANK_CHECK = {
    "shadowed": [{"rule": "r2", "by": ["r1"]}],
    "overlaps": [{"a": "r1", "b": "r2", "example": {"description": "UBEREATS", "amount": 12.5}}],
}

SAMPLE_EVAL = {
    "as_of": "2026-10-18T09:40:00-07:00",
    "n_heldout": 150,
    "systems": [
        {"name": "Keyword rules", "accuracy": 0.61, "citation_f1": 0.42, "rerun_agreement": 1.0,
         "median_latency_ms": 2, "cost_per_1k_usd": 0.0, "questions_per_txn": 0.0},
        {"name": "LLM judge", "accuracy": 0.78, "citation_f1": 0.55, "rerun_agreement": 0.83,
         "median_latency_ms": 1900, "cost_per_1k_usd": 4.1, "questions_per_txn": 0.0},
        {"name": "LLM facts + Z3", "accuracy": 0.9, "citation_f1": 0.86, "rerun_agreement": 0.95,
         "median_latency_ms": 700, "cost_per_1k_usd": 0.9, "questions_per_txn": 0.25},
        {"name": "Jev + Z3", "accuracy": 0.94, "citation_f1": 0.91, "rerun_agreement": 1.0,
         "median_latency_ms": 140, "cost_per_1k_usd": 0.32, "questions_per_txn": 0.18},
    ],
}

SAMPLE_RELOAD = {"transactions": 0, "employees": 0, "extractions": 0, "approvals": 0, "skipped": []}
SAMPLE_HEALTH = {"ok": True, "policy_version": STUB_VERSION, "stub": True}
