# Proof of Purchase: Person A (Z3 engine + FastAPI) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the Z3 rule engine and the FastAPI server that the dashboard, the ASI:One agent and the evaluation all call, in the order the hackathon gates need: every route stubbed by 15:00, real `/check` → approve → authorize by 20:00, ledger/policy/bank-rule audits by 02:00.

**Architecture:** `engine/` compiles JSON rules into Z3 formulas once per policy version and answers check / fix / questions / audit for one transaction with a handful of small solver calls. `api/` wraps it in FastAPI with stdlib `sqlite3`, assembles facts from Person B's extractor and data files, and renders every result as the one `case` shape. Explanations are filled from templates using rule text, never free-written by a model.

**Tech Stack:** Python 3.11, `z3-solver`, FastAPI, Pydantic v2, uvicorn, `sqlite3` (stdlib), pytest.

**Spec:** `Proof of Purchase Build Guide.md` (repo root). **API contract handed to Person B:** `API_CONTRACT.md` (repo root; live copy with comments at https://claude.ai/code/artifact/db9e4ece-6838-4ae3-9755-23881fe59240). The shapes there and in `api/models.py` must stay identical.

## Global Constraints

- Python 3.11. Dependencies live in `pyproject.toml` `[project.dependencies]` at the repo root (Person B created it with `z3-solver`, `pydantic`, `httpx`); Task 1 adds `fastapi`, `uvicorn[standard]`, `pytest`, `sentry-sdk[fastapi]` there. Install with `pip install -e .`. There is no `requirements.txt`.
- Z3 makes every decision. A model (Jev) only produces per-fact probabilities; no model output ever changes a verdict directly.
- A fact from probabilities is **known** only when `p >= 0.85` or `p <= 0.15`; otherwise it is unknown and stays a free Z3 variable.
- Enum facts are Z3 `Int` (index into the value list); `amount` is Z3 `Real`; `hour`, `days_since_purchase` are `Int`; everything in the policy engine stays in linear arithmetic. Only `bank_rules.py` uses the string theory.
- Fix effort weights (soft-constraint weights in `z3.Optimize`): `coded_account` 1, `receipt_attached` 1, `pre_approved` 2, `amount` 3. Immutable (hard): `role`, `expense_kind`, `hour`, `days_since_purchase`, `client_present`, `at_company_event`.
- Explanations come from templates in `api/explain.py` using each rule's `text` and `because` facts.
- `proof_hash` = SHA-256 hex of `json.dumps({"facts": {name: value}, "policy_version": v, "verdict": s}, sort_keys=True)`.
- Secrets only through the shared `.env` (`TYPESAFE_API_KEY`, `GEMINI_API_KEY`, `AGENT_SEED`, `SENTRY_DSN`, `API_URL`); `.env` is never committed, `.env.example` is.
- Lane boundary: A edits only `engine/`, `api/`, `.env.example`, `.github/`, and these shared root files by appending only: `pyproject.toml` (dependencies and `testpaths`), `README.md`, `.gitignore`. Files under `data/`, `extract/`, `eval/`, `agent/` are Person B's: import them, never edit them. If a B module is missing, the API must still start (fallbacks below).
- Person B's commit `3d73e5e` already put `jev_z3/`, `tests/`, `bin/`, `examples/`, `policy_store.json`, `pyproject.toml`, `README.md` and `.gitignore` on `main`. Never edit anything under `jev_z3/`, `tests/`, `bin/`, `examples/`. `pyproject.toml` pins `testpaths = ["tests"]`, so Task 1 changes it to `["engine", "api", "tests"]`; after that a bare `pytest -q` runs everything. `README.md` exists, so Task 1 appends a `## Proof of Purchase API` section. The API never imports `jev_z3`: importing its `PolicyStore` writes `policy_store.json` into the working directory, and its `SpendCategory` enum is not the contract's `expense_kind`. The API imports only `extract.jev` and `extract.mapping`, with Task 8's fallbacks until they exist.
- Timestamps: ISO 8601 strings; a naive timestamp is treated as `America/Los_Angeles`. A date-only string (`2026-09-30`, no time part) gives a midnight datetime but `hour` stays **unknown**; otherwise rule 6.2 (meals before 6am) fires on every meal in a date-only ledger.
- Thresholds: `facts_from_probs` defaults come from `POP_P_HI` / `POP_P_LO` (default 0.85 / 0.15) so B's tuned numbers reach production without a code change.
- Concurrency: FastAPI runs sync routes in a thread pool. Z3 contexts are not thread-safe, so every public `Policy` method and `check_bank_rules` holds one module-level `threading.RLock` (`engine/rules.py:ENGINE_LOCK`). SQLite connections are opened per request (`db.connect()` inside the route, closed after); never a module-global connection.
- Input validation at the API boundary: a value outside its fact's domain (`amount <= 0`, `hour` not in 0–23, an enum string not in `values`) is a 422, never a solver call. Otherwise the domain constraints make every rule unsat and the case reads "all 24 rules violated".
- The build guide mentions starter `engine/rules.py` and nine tests; the repo has none, so Task 2 writes the engine from scratch.

## Review Focus

1. `POST /check` with no `amount` and no `$…` in the text → `amount` stays unknown; verdict `undetermined`, `questions` holds one entry for `amount`, explanation names the missing amount. No crash. (Task 8)
2. `POST /check` with an `employee_id` not in the employees table → 404 `{"detail": "unknown employee"}`, never 500. (Task 8)
3. `POST /cases/{id}/authorize` on a non-compliant case → 409; on a compliant case whose `amount` is still unknown → 409 `{"detail": "amount unknown"}` (reachable: "Team dinner, not sure of the price" → `/approve` → `/answer receipt_attached`); called twice on a compliant case → the same `auth_id` and `proof_hash`. (Task 8)
4. `POST /cases/{id}/answer` with a fact not in the schema, a wrong value type, a value outside the fact's domain (`amount: -1`, `hour: 99`, `expense_kind: "snack"`), or `fact == "pre_approved"` → 422 (only `/approve` sets pre-approval). `POST /check` with `amount <= 0` → 422. (Task 8)
5. A ledger transaction with no extraction row, or every probability between 0.15 and 0.85 → `undetermined`, counted in the audit, never an exception; the audit never aborts on one bad row. (Task 9)
6. A refund or credit (`amount <= 0`) in `transactions.csv` → skipped at load with a reason in the reload response, never audited as "every rule violated" because the amount domain fails. A blank `receipt_attached` cell → the fact is unknown, never `false`. (Task 14)
7. Person B drops new rows into `data/transactions.csv` while the API runs → `POST /data/reload` picks them up and the next audit decides only the new rows; a verdict for an unchanged row is untouched, a verdict for a row whose columns or extraction changed is dropped and re-decided. (Task 14)
8. The whole suite passes at 03:00 Los Angeles time and on October 31: every `/check` in a test passes a fixed `timestamp` so `hour` and `days_since_purchase` never come from the wall clock. (Task 8)
9. Two requests at once (the agent polling `GET /cases/{id}` while the dashboard posts `/check`) never crash the process: the engine lock serializes Z3. (Task 8)

---

## File structure

```
engine/
  __init__.py
  schema.py             FACTS: name -> (kind, values, lo, hi, mutable, weight, derived)
  rules.py              compile_expr, Policy (check, fix, questions, required_values, decide, audit, disagreement), facts_from_probs, load_policy
  bank_rules.py         check_bank_rules
  keyword_baseline.py   extract_stub (offline fallback extractor), txn_row, CODED_FALLBACK, keyword_verdict (eval baseline)
  demo_policy.json      company rules (seed in Task 2, full in Task 10)
  irs_pack.json         IRS meal / entertainment / receipt rules + account-coding rules
  test_rules.py  test_bank_rules.py  test_policy_packs.py  test_keyword_baseline.py
api/
  __init__.py
  main.py            FastAPI app: CORS, startup (load policy, init DB, load B's files), include_router x5; no routes of its own
  routes_cases.py    /check, /cases/{id}, /cases, /answer, /approve, /authorize   (stubs Task 1, real Task 8)
  routes_ledger.py   /ledger, /ledger/audit, /data/reload                        (Tasks 9, 14)
  routes_policy.py   /policy, /policy/audit, /policy/what-if                     (Tasks 10, 13)
  routes_bank.py     /bank-rules/check                                           (Task 11)
  routes_eval.py     /eval, /health                                              (Task 12)
  models.py     Pydantic request/response models = the contract
  samples.py    the sample JSON every stub returns (Task 1), kept for tests
  db.py         sqlite3 schema, queries, loaders for data/*.csv and data/extractions.jsonl
  cases.py      facts assembly, decide, case JSON, answer / approve / authorize, decide_transaction
  explain.py    templates: explanation, question text, merchant category per expense kind
  ledger.py     ledger rows and the cached audit
  conftest.py   the `client` fixture (TestClient as a context manager, POP_DB and POP_DATA_DIR in tmp_path) + Task 8's fake extractor
  test_api.py (smoke, Task 1 only)  test_db.py  test_explain.py  test_cases.py  test_ledger.py  test_policy.py  test_bank.py  test_eval.py
.github/workflows/test.yml    pytest -q on every push
pyproject.toml  README.md  .gitignore  (Person B's; Task 1 appends to them)   .env.example
```

One router module per domain so parallel workers never edit the same file. `api/main.py`, `api/models.py`, `api/samples.py` and `api/test_api.py` are written in Task 1 and frozen after it: a change to any of them is a contract change and is announced first. (`api/conftest.py` is not frozen: Task 8 adds a fixture to it.)

Person B's files the API reads (their columns are pinned in the contract doc): `data/employees.csv`, `data/approvals.csv`, `data/transactions.csv`, `data/extractions.jsonl`, `eval/results.json`, `extract/jev.py:extract(text)`, `extract/mapping.py:coded_account_for(qb_category)`.

---

### Task 1: Repo skeleton and every route as a stub (gate 15:00)

**Files:**
- Create: `.env.example`, `.github/workflows/test.yml`,
- Append to (Person B's files): `pyproject.toml`, `README.md`, `.gitignore`
- Create: `engine/__init__.py`, `api/__init__.py`, `api/models.py`, `api/samples.py`, `api/main.py`, `api/routes_cases.py`, `api/routes_ledger.py`, `api/routes_policy.py`, `api/routes_bank.py`, `api/routes_eval.py`
- Test: `api/test_api.py`, `api/conftest.py`

**Interfaces:**
- Produces `app: FastAPI` in `api/main.py` and `router: APIRouter` in each of the five `api/routes_*.py` modules; `main.py` only includes them. Produces `samples.stub(payload: dict) -> JSONResponse` (adds `X-Stub: 1`).
- Produces in `api/models.py` (Pydantic v2): `CheckRequest(text: str, employee_id: str, amount: float | None = None, timestamp: str | None = None)`, `AnswerRequest(fact: str, value: bool | str | float)`, `ApproveRequest(approver: str, approved: bool)`, `AuditRequest(company: str)`, `BankRule(id: str, contains: list[str], amount_min: float | None = None, amount_max: float | None = None, category: str)`, `BankRulesRequest(rules: list[BankRule])`, `Fact(value: bool | str | float | int | None, source: Literal["jev","user","text","employee","approvals","ledger","derived","rules","answer"], p: float | None = None)`, `Violation(rule: str, layer: str, text: str, because: list[str])`, `FixStep(fact: str, from_: ... = Field(alias="from"), to: ...)`, `Question(fact: str, text: str, p: float | None = None, options: list[str] | None = None)`, `Authorization(auth_id: str, amount_limit: float, merchant_category: str, expires_at: str, proof_hash: str)`, `Approval(approver: str, approved: bool, at: str)`, `Case(case_id, created_at, employee_id, text, policy_version, verdict: Literal["compliant","violation","undetermined"], facts: dict[str, Fact], violations: list[Violation], applied: list[str], fix: list[FixStep] | None, questions: list[Question], explanation: str, awaiting_approval: bool, approval: Approval | None, authorization: Authorization | None)`, `CaseList(cases: list[Case])`, `LedgerRow(txn_id, company, employee_id, vendor, memo, amount, timestamp, qb_category, coded_account, verdict, violations: list[str], case: Case | None)`, `LedgerOut(transactions: list[LedgerRow], total: int)`, `RuleCount(rule: str, text: str, count: int)`, `AuditSummary(company, policy_version, n: int, by_verdict: dict[str,int], by_rule: list[RuleCount], top_violations: list[LedgerRow], elapsed_ms: int)`, `PolicyOut(version: str, rules: list[dict], facts: dict)`, `Conflict(a: str, b: str, example: dict)`, `PolicyAudit(dead: list[str], conflicts: list[Conflict])`, `Shadowed(rule: str, by: list[str])`, `Overlap(a: str, b: str, example: dict)`, `BankRulesOut(shadowed: list[Shadowed], overlaps: list[Overlap])`, `EvalSystem(name, accuracy, citation_f1, rerun_agreement, median_latency_ms, cost_per_1k_usd, questions_per_txn)`, `EvalOut(as_of: str | None, n_heldout: int, systems: list[EvalSystem])`, `Health(ok: bool, policy_version: str, stub: bool)`.
- Produces in `api/samples.py`: `SAMPLE_CASE` (the spec's case JSON with `case_id "c_8f2a1b3c"`, `created_at "2026-10-17T19:30:00-07:00"`, `employee_id "e_newhire"`, `text "Client dinner Thursday with Acme's CFO, about $48."`, `policy_version "stub00000000"`, `applied []`, `awaiting_approval true`, `approval null`, `authorization null`, each violation carrying `layer`), `SAMPLE_AUTH`, `SAMPLE_LEDGER_ROW`, `SAMPLE_AUDIT`, `SAMPLE_POLICY`, `SAMPLE_POLICY_AUDIT`, `SAMPLE_BANK_CHECK`, `SAMPLE_EVAL`. All validate against their models (`Case.model_validate(SAMPLE_CASE)` in a test).

- [ ] **Step 1: Write the failing tests**

```python
# api/conftest.py  (shared by every api/test_*.py; Task 8 adds the extractor and DB fixtures here)
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("POP_DB", str(tmp_path / "t.db"))          # read at call time by db.connect (Task 6)
    monkeypatch.setenv("POP_DATA_DIR", str(tmp_path / "nodata"))  # no B files: the employee seed applies
    from api.main import app
    with TestClient(app) as c:   # the context manager is what runs startup; a bare TestClient(app) never does
        yield c

# api/test_api.py
import pytest
from api import samples, models
ROUTES = [
    ("post", "/check", {"text": "Client dinner $48", "employee_id": "e_newhire"}),
    ("get", "/cases/c_8f2a1b3c", None),
    ("get", "/cases?awaiting_approval=true", None),
    ("post", "/cases/c_8f2a1b3c/answer", {"fact": "at_company_event", "value": False}),
    ("post", "/cases/c_8f2a1b3c/approve", {"approver": "e_manager", "approved": True}),
    ("post", "/cases/c_8f2a1b3c/authorize", None),
    ("get", "/ledger", None),
    ("post", "/ledger/audit", {"company": "demo"}),
    ("get", "/policy", None),
    ("post", "/policy/audit", None),
    ("post", "/bank-rules/check", {"rules": []}),
    ("get", "/eval", None),
    ("get", "/health", None),
]
@pytest.mark.parametrize("method,path,body", ROUTES)
def test_every_route_answers_as_stub(client, method, path, body):
    r = client.request(method.upper(), path, json=body)
    assert r.status_code == 200
    # X-Stub is checked by curl in Step 6; each per-module test asserts its absence once that route is real

def test_check_stub_is_the_spec_case(client):
    c = client.post("/check", json=ROUTES[0][2]).json()
    assert c["verdict"] == "violation"
    assert c["violations"][0]["rule"] == "3.4"
    assert c["fix"][0] == {"fact": "pre_approved", "from": False, "to": True}
    assert c["awaiting_approval"] is True

def test_samples_match_models():
    models.Case.model_validate(samples.SAMPLE_CASE)
    models.AuditSummary.model_validate(samples.SAMPLE_AUDIT)
    models.BankRulesOut.model_validate(samples.SAMPLE_BANK_CHECK)
    models.EvalOut.model_validate(samples.SAMPLE_EVAL)
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest -q api/test_api.py`  Expected: FAIL, `ModuleNotFoundError: api`

- [ ] **Step 3: Edit `pyproject.toml`, write `.env.example`, append to `.gitignore`**

`pyproject.toml`: add `fastapi`, `uvicorn[standard]`, `pytest`, `sentry-sdk[fastapi]` to `[project.dependencies]` (`z3-solver`, `pydantic`, `httpx` are already there) and set `[tool.pytest.ini_options] testpaths = ["engine", "api", "tests"]` (keep `pythonpath = ["."]`). Then `pip install -e .`. `.env.example`: the five keys with empty values and `API_URL=http://localhost:8000`. `.gitignore`: append `*.db` (the rest is already there).

- [ ] **Step 4: Write `api/models.py` with the models listed in Interfaces**

`FixStep` uses `Field(alias="from")` with `populate_by_name=True` so JSON says `from`. Every response model has `model_config = ConfigDict(populate_by_name=True)`.

- [ ] **Step 5: Write `api/samples.py` and `api/main.py`**

`main.py`: `if os.environ.get("SENTRY_DSN"): sentry_sdk.init(dsn=os.environ["SENTRY_DSN"], traces_sample_rate=1.0)` (the build guide gives Person C "Sentry on web and API"; this hook means C never edits our files), `app = FastAPI(title="Proof of Purchase API")`, `CORSMiddleware(allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])`, then `app.include_router(m.router)` for the five `routes_*` modules. Each `routes_*.py`: `router = APIRouter()` and one function per route it owns (see the file structure), returning `stub(sample)` from `api/samples.py`. `GET /health` (in `routes_eval.py`) returns `{"ok": true, "policy_version": "stub00000000", "stub": true}`.

- [ ] **Step 6: Run tests, then the server**

Run: `pytest -q api/`  Expected: all PASS. Then `uvicorn api.main:app --port 8000` and `curl -i localhost:8000/health`  Expected: `X-Stub: 1` in the headers.

- [ ] **Step 7: CI and README**

`.github/workflows/test.yml`: on push, `actions/setup-python@v5` with `python-version: "3.11"`, `pip install -e .`, `pytest -q`. `README.md` is Person B's (it describes Jev-Z3 and gets rewritten by everyone in the 10:30 window); append a `## Proof of Purchase API` section: what it does (two sentences from the spec), how to run (`python -m venv .venv && source .venv/bin/activate && pip install -e . && uvicorn api.main:app --reload --port 8000`), link to the contract doc, a "Changes to Intuit's data" heading left empty for B.

- [ ] **Step 8: Commit and push; tell C the stub is deployable and B the contract link**

```bash
git add -A && git commit -m "feat: repo skeleton, API contract models, every route stubbed" && git push -u origin main
```

---

### Task 2: Fact schema and rule compiler

**Files:**
- Create: `engine/schema.py`, `engine/rules.py`, `engine/demo_policy.json` (seed), `engine/irs_pack.json` (seed)
- Test: `engine/test_rules.py`

**Interfaces:**
- Produces `schema.FactSpec = NamedTuple(kind: Literal["enum","real","int","bool"], values: tuple[str, ...] | None, lo: int | None, hi: int | None, mutable: bool, weight: int, derived: bool)` and `schema.FACTS: dict[str, FactSpec]` in this order with these values:

| name | kind | values / range | mutable | weight | derived |
| --- | --- | --- | --- | --- | --- |
| role | enum | employee, contractor, intern | no | – | no |
| expense_kind | enum | meal, rideshare, airfare, hotel, software, equipment, entertainment, other | no | – | no |
| coded_account | enum | meals_50, meals_100, entertainment_0, travel, office, other | yes | 1 | yes |
| amount | real | ≥ 0 (USD) | yes | 3 | no |
| hour | int | 0–23 | no | – | no |
| days_since_purchase | int | ≥ 0 | no | – | no |
| receipt_attached | bool | | yes | 1 | no |
| pre_approved | bool | | yes | 2 | no |
| client_present | bool | | no | – | no |
| at_company_event | bool | | no | – | no |

- Produces `schema.validate_value(name: str, value) -> object`: the API's one domain check. Unknown name → `KeyError`; bool kind needs a `bool`; enum kind needs a `str` in `values`; real kind needs a non-bool number with `value > 0` (amount is money); int kind needs a non-bool number with `float(value).is_integer()` inside `lo..hi`; returns the value coerced (`int` for int kinds, `float` for real). Anything else → `ValueError(f"{name}: {reason}")`. Task 8 turns the two exceptions into 422s.
- Produces in `rules.py`: `ENGINE_LOCK = threading.RLock()` (every public `Policy` method and `bank_rules.check_bank_rules` run under `with ENGINE_LOCK:`; Z3's shared context is not thread-safe and FastAPI serves routes from a thread pool; re-entrant because `decide` calls `check`); `Rule = NamedTuple(id: str, layer: str, text: str, when: z3.BoolRef, require: z3.BoolRef, formula: z3.BoolRef, raw: dict)`; `compile_expr(expr, vars: dict[str, z3.ExprRef]) -> z3.ExprRef`; `class Policy` with `__init__(self, rules: list[dict])`, attributes `rules: list[Rule]`, `by_id: dict[str, Rule]`, `vars: dict[str, z3.ExprRef]`, `dom: list[z3.BoolRef]`, `all_formulas: z3.BoolRef` (`And(*[r.formula for r in rules])`, built once), `version: str` (`hashlib.sha256(json.dumps(rules, sort_keys=True).encode()).hexdigest()[:12]`); `load_policy(*paths: str) -> Policy` (concatenates the JSON lists); `to_z3(name: str, value) -> z3.ExprRef` (enum string → `IntVal(index)`, bool → `BoolVal`, real → `RealVal(str(value))`, int → `IntVal`); `from_z3(name: str, v: z3.ExprRef) -> object` (inverse, `Real` → `float(v.as_fraction())`). In `compile_expr`, pick the operator with a dict of `operator.eq/ne/gt/ge/lt/le` and apply only the chosen one; building all six eagerly raises `TypeError` on a bool fact (`{"eq": ["client_present", true]}` in rule 6.5).
- Rule JSON grammar (from the spec): `{"id", "layer": "company"|"irs", "text", "when": <expr>, "require": <expr> | "<bool fact name>" | true | false}`. `<expr>` is `{"and": [...]}`, `{"or": [...]}`, `{"not": <expr>}`, `{"eq"|"neq"|"gt"|"ge"|"lt"|"le": ["<fact>", <literal>]}`, `{"in": ["<fact>", [<literal>, ...]]}`, or a bare `"<bool fact name>"`. `formula = Implies(when, require)`. `dom` holds `0 <= v < len(values)` per enum, `0 <= hour <= 23`, `days >= 0`, `amount >= 0`.

- [ ] **Step 1: Write the failing tests**

```python
# engine/test_rules.py
import z3, pytest
from engine.rules import Policy, compile_expr, load_policy, to_z3
RULE_5_2 = {"id": "5.2", "layer": "company",
  "text": "Interns get no transport reimbursement except at company events.",
  "when": {"and": [{"eq": ["role", "intern"]}, {"in": ["expense_kind", ["rideshare", "airfare"]]}]},
  "require": "at_company_event"}

def test_compiles_rule_5_2_and_it_bites():
    p = Policy([RULE_5_2])
    assert p.rules[0].id == "5.2" and p.rules[0].layer == "company"
    s = z3.Solver(); s.add(*p.dom, p.rules[0].formula)
    s.add(p.vars["role"] == to_z3("role", "intern"), p.vars["expense_kind"] == to_z3("expense_kind", "rideshare"), p.vars["at_company_event"] == False)
    assert s.check() == z3.unsat

def test_require_may_be_an_expression_or_false():
    p = Policy([{"id": "x", "layer": "irs", "text": "t", "when": {"eq": ["expense_kind", "meal"]}, "require": {"eq": ["coded_account", "meals_50"]}},
                {"id": "y", "layer": "company", "text": "t", "when": {"eq": ["role", "contractor"]}, "require": False}])
    assert len(p.rules) == 2

def test_unknown_fact_and_value_raise():
    p = Policy([])
    with pytest.raises(KeyError): compile_expr({"eq": ["colour", "red"]}, p.vars)
    with pytest.raises(ValueError): compile_expr({"eq": ["role", "ceo"]}, p.vars)

def test_version_is_12_hex_and_stable():
    a, b = Policy([RULE_5_2]), Policy([RULE_5_2])
    assert a.version == b.version and len(a.version) == 12

def test_load_policy_reads_both_packs():
    p = load_policy("engine/demo_policy.json", "engine/irs_pack.json")
    assert {"3.4", "5.2", "IRS-meal"} <= set(p.by_id)
```

- [ ] **Step 2: Run to verify it fails**  Run: `pytest -q engine/test_rules.py`  Expected: FAIL, `ModuleNotFoundError: engine.rules`

- [ ] **Step 3: Write `engine/schema.py`** with the table above.

- [ ] **Step 4: Write `compile_expr`, `to_z3`, `from_z3`, `Policy.__init__`, `load_policy` in `engine/rules.py`**

Build `vars` from `FACTS` (`z3.Int`, `z3.Real`, `z3.Bool`). `compile_expr` recurses on the one-key dict; an unknown fact → `KeyError(name)`; an enum literal not in its values → `ValueError`.

- [ ] **Step 5: Seed the packs** — `engine/demo_policy.json`: rules `3.4` (*Any expense over $35 needs manager pre-approval.* `when {"gt": ["amount", 35]}` require `pre_approved`) and `5.2` (above). `engine/irs_pack.json`: these seven rules from Task 10's table: `IRS-meal`, `IRS-meal-event`, `IRS-ent`, `IRS-travel`, `IRS-office`, `IRS-other`, `IRS-receipt-60`.

- [ ] **Step 6: Run tests**  Run: `pytest -q engine/`  Expected: PASS

- [ ] **Step 7: Commit**  `git commit -am "feat(engine): fact schema and JSON rule compiler"`

---

### Task 3: Verdicts with cited facts: `Policy.check`

**Files:** Modify `engine/rules.py`; Test `engine/test_rules.py`

**Interfaces:**
- Produces `Verdict = NamedTuple(status: Literal["compliant","violation","undetermined"], violations: list[Violation], applied: list[str])`, `Violation = NamedTuple(rule: str, because: list[str])`, `Policy.facts_eq(facts: dict) -> dict[str, z3.BoolRef]` (name → `var == to_z3(name, value)`), `Policy.check(facts: dict[str, object]) -> Verdict`.
- Algorithm (the spec's three steps, pinned; measured against the full 24-rule pack: the naive per-rule loop costs ~22 ms per compliant row, about 27 s for Intuit's 1,240 rows, so the joint check comes first):
  0. **Joint check first.** `sat(dom, facts_eq, all_formulas)` → no rule is violated on its own, skip step 1. (If every rule is individually satisfiable then so is this conjunction's failure only through combinations, which step 2 reports as `undetermined`; the result is identical to running step 1, just 24 solver calls cheaper on every compliant row.)
  1. Per rule, only when step 0 was `unsat`: `s = z3.Solver(); s.set(unsat_core=True); s.set("core.minimize", True); s.add(*dom, rule.formula)`; for each known fact `s.assert_and_track(eq, z3.Bool(f"fact_{name}"))`; `unsat` → violated with `because = sorted(name for b in s.unsat_core())` (strip the `fact_` prefix). If any violated → `violation`.
  2. Else `s.add(*dom, *facts_eq, Not(all_formulas))`: `unsat` → `compliant`; `sat` → `undetermined`.
  3. `applied` (compliant only): for each rule, `w = z3.simplify(z3.substitute(r.when, *[(vars[n], to_z3(n, v)) for n, v in facts.items()]))`; `z3.is_true(w)` → applied, `z3.is_false(w)` → not, otherwise (an unknown fact is in the condition) ask the solver: `unsat(dom, facts_eq, Not(r.when))`. Substitution settles nearly every rule without a solver call.

- [ ] **Step 1: Write the failing tests**

```python
DINNER = dict(role="employee", expense_kind="meal", client_present=True, at_company_event=False,
              amount=48, hour=19, days_since_purchase=0, pre_approved=False, coded_account="travel")
P = load_policy("engine/demo_policy.json", "engine/irs_pack.json")

def test_dinner_breaks_two_rules_and_cites_facts():
    v = P.check(DINNER)
    assert v.status == "violation"
    by = {x.rule: x.because for x in v.violations}
    assert by["3.4"] == ["amount", "pre_approved"]
    assert set(by["IRS-meal"]) == {"expense_kind", "at_company_event", "coded_account"}

def test_cheap_coded_dinner_is_proven_compliant():
    v = P.check({**DINNER, "amount": 30, "coded_account": "meals_50"})
    assert v.status == "compliant" and "IRS-meal" in v.applied and "3.4" not in v.applied

def test_unknown_pre_approval_is_undetermined():
    f = {k: v for k, v in DINNER.items() if k != "pre_approved"}
    assert P.check({**f, "coded_account": "meals_50"}).status == "undetermined"
```

- [ ] **Step 2: Run to verify it fails**  Expected: `AttributeError: 'Policy' object has no attribute 'check'`
- [ ] **Step 3: Implement `facts_eq` and `check`** as pinned above.
- [ ] **Step 4: Run tests**  Run: `pytest -q engine/`  Expected: PASS
- [ ] **Step 5: Commit**  `git commit -am "feat(engine): check() with per-rule unsat cores"`

---

### Task 4: Probabilities → facts, the required account, the one question, `decide`

**Files:** Modify `engine/rules.py`; Test `engine/test_rules.py`

**Interfaces:**
- Produces `facts_from_probs(probs: dict[str, dict], hi: float | None = None, lo: float | None = None) -> dict[str, object]`; `None` → `float(os.environ.get("POP_P_HI", 0.85))` / `float(os.environ.get("POP_P_LO", 0.15))`, read at call time so B's tuned thresholds apply to `/check` and the audit without a code change. Input entry shapes (this is Person B's `extract()` output, pinned in the contract): enum fact `{"value": "meal", "p": 0.97}` → kept when `p >= hi`; bool fact `{"p": 0.91}` where `p` = P(yes) → `True` when `p >= hi`, `False` when `p <= lo`; everything else omitted.
- Produces `Policy.required_values(facts: dict, fact: str) -> list[str]`: enum values `v` such that `dom + [r.formula for r in rules if fact in json.dumps(r.raw)] + facts_eq + (var == v)` is sat, in enum order. Only rules that mention the fact are used, so a violation elsewhere (e.g. missing pre-approval) does not hide which account the coding rules require.
- Produces `Policy.resolve(facts: dict) -> tuple[dict, dict[str, str]]`: for each `derived` enum fact not in `facts`, if `required_values` has exactly one element set it; the second return maps the fact to the id of the first rule mentioning it whose `when` is entailed (`unsat(dom, facts_eq, Not(when))`).
- Produces `Policy.questions(facts: dict, probs: dict[str, dict]) -> list[str]`: for each bool fact not in `facts`, run `resolve` + `check` with it `True` and with it `False`; keep it if the two branches differ in `status`, in the set of violated rule ids, or in resolved derived values; sort by `abs(probs.get(f, {}).get("p", 0.5) - 0.5)` ascending.
- Produces `Decision = NamedTuple(facts: dict, derived: dict[str, str], verdict: Verdict, fix: list[FixStep] | None, questions: list[str])` and `Policy.decide(facts: dict, probs: dict[str, dict]) -> Decision` = `resolve` → `check` → `fix` only when `violation` (Task 5; until then return `[]`) → `questions` only when `undetermined`.

- [ ] **Step 1: Write the failing tests**

```python
def test_facts_from_probs_thresholds():
    probs = {"expense_kind": {"value": "meal", "p": 0.97}, "client_present": {"p": 0.91},
             "at_company_event": {"p": 0.08}, "receipt_attached": {"p": 0.5}}
    assert facts_from_probs(probs) == {"expense_kind": "meal", "client_present": True, "at_company_event": False}

UNCODED = {k: v for k, v in DINNER.items() if k != "coded_account"}

def test_required_account_for_a_client_dinner_is_meals_50():
    assert P.required_values(UNCODED, "coded_account") == ["meals_50"]
    unknown_event = {k: v for k, v in UNCODED.items() if k != "at_company_event"}
    assert P.required_values(unknown_event, "coded_account") == ["meals_50", "meals_100"]

def test_resolve_sets_the_account_and_names_the_rule():
    facts, derived = P.resolve(UNCODED)
    assert facts["coded_account"] == "meals_50" and derived == {"coded_account": "IRS-meal"}

def test_question_is_asked_only_when_it_decides():
    ride = dict(role="intern", expense_kind="rideshare", amount=20, hour=9, days_since_purchase=0, pre_approved=True)
    assert P.questions(ride, {"at_company_event": {"p": 0.4}}) == ["at_company_event"]
    assert P.questions({k: v for k, v in UNCODED.items() if k != "client_present"}, {}) == []  # 3.4 broken either way

def test_decide_on_the_demo_dinner():
    d = P.decide(UNCODED, {})
    assert d.facts["coded_account"] == "meals_50" and d.derived == {"coded_account": "IRS-meal"}
    assert d.verdict.status == "violation" and [v.rule for v in d.verdict.violations] == ["3.4"]
```

- [ ] **Step 2: Run to verify it fails**  Expected: `ImportError: facts_from_probs`
- [ ] **Step 3: Implement the five functions** as pinned.
- [ ] **Step 4: Run tests**  Run: `pytest -q engine/`  Expected: PASS
- [ ] **Step 5: Commit**  `git commit -am "feat(engine): facts_from_probs, required account, questions, decide"`

---

### Task 5: The smallest fix: `Policy.fix`

**Files:** Modify `engine/rules.py`; Test `engine/test_rules.py`

**Interfaces:**
- Produces `FixStep = NamedTuple(fact: str, from_: object, to: object)` and `Policy.fix(facts: dict) -> list[FixStep] | None`.
- Algorithm (pinned): `o = z3.Optimize(); o.add(*dom, *[r.formula for r in rules])`; known immutable facts → `o.add(eq)`; known mutable facts → `o.add_soft(eq, weight=FACTS[name].weight)`; unknown facts stay free and are never reported. `o.check() == unsat` → `None`. Else steps = mutable known facts whose model value differs, sorted by weight descending then schema order. If `amount` is among them: second `Optimize` with the same hard constraints, every other mutable fact pinned to its first-pass value, `amount <= current`, and money in whole cents: `cents = z3.Int("cents"); o2.add(vars["amount"] * 100 == cents); h = o2.maximize(cents)`; `to = o2.model()[cents].as_long() / 100`. Maximizing the Real directly is wrong on an open bound: for `amount < 75` Z3 reports the optimum as `75 - epsilon` and the model holds an arbitrary value such as 74, so the fix would read "at or under $74"; with integer cents the bound is closed and the answer is 74.99. (Rule 3.4's `gt amount 35` is a closed bound after negation, so its answer is exactly 35 either way.)

- [ ] **Step 1: Write the failing tests**

```python
def test_fix_for_the_dinner_is_approval_then_recode():
    assert P.fix(DINNER) == [FixStep("pre_approved", False, True), FixStep("coded_account", "travel", "meals_50")]

def test_no_fix_when_only_immutable_facts_are_wrong():
    ride = dict(role="intern", expense_kind="rideshare", at_company_event=False, amount=20, hour=9,
                days_since_purchase=0, pre_approved=True, receipt_attached=True, coded_account="travel")
    assert P.fix(ride) is None

def test_amount_fix_reads_as_at_or_under():
    # rule 6.4 (Task 10): entertainment over $100 is never reimbursed; pre-approval cannot help
    ent = dict(role="employee", expense_kind="entertainment", amount=150, hour=20, days_since_purchase=0,
               pre_approved=True, receipt_attached=True, coded_account="entertainment_0", client_present=True, at_company_event=False)
    assert P.fix(ent) == [FixStep("amount", 150, 100.0)]
```

Add rule `6.4` to `engine/demo_policy.json` now (it is in Task 10's table).

- [ ] **Step 2: Run to verify it fails**  Expected: `AttributeError: fix`
- [ ] **Step 3: Implement `fix`** and wire it into `decide`.
- [ ] **Step 4: Run tests**  Expected: PASS
- [ ] **Step 5: Commit**  `git commit -am "feat(engine): smallest fix via z3.Optimize with effort weights"`

---

### Task 6: Database and Person B's data files

**Files:** Create `api/db.py`; Test `api/test_db.py`

**Interfaces:**
- Produces: `connect(path: str | None = None) -> sqlite3.Connection` (`path or os.environ.get("POP_DB", "pop.db")` resolved **inside** the function, never as a default argument, so a test's `monkeypatch.setenv("POP_DB", ...)` works after import; `row_factory = sqlite3.Row`; calls `init` itself, so a route that opens a connection never depends on the startup hook having run). Routes open one connection per request and close it (`with closing(db.connect()) as conn:`); a module-global connection breaks under FastAPI's thread pool (`check_same_thread`). `init(conn)` creating, idempotently (`CREATE TABLE IF NOT EXISTS`), and seeding the four demo employees below when `employees` is empty:
  - `cases(case_id TEXT PK, created_at TEXT, employee_id TEXT, text TEXT, amount REAL, timestamp TEXT, answers_json TEXT, case_json TEXT, policy_version TEXT, awaiting_approval INTEGER)`
  - `transactions(txn_id TEXT PK, company TEXT, employee_id TEXT, vendor TEXT, memo TEXT, amount REAL, timestamp TEXT, qb_category TEXT, coded_account TEXT, receipt_attached INTEGER, receipt_date TEXT, source TEXT, extraction_json TEXT)`
  - `verdicts(txn_id TEXT, policy_version TEXT, verdict TEXT, case_json TEXT, PRIMARY KEY(txn_id, policy_version))` (`verdict` is a column so `GET /ledger?verdict=` filters and counts in SQL)
  - `approvals(id INTEGER PK AUTOINCREMENT, case_id TEXT, txn_id TEXT, approver TEXT, approved INTEGER, at TEXT)`
  - `policy_versions(version TEXT PK, rules_json TEXT, loaded_at TEXT)`
  - `employees(employee_id TEXT PK, name TEXT, role TEXT, manager_id TEXT)`
- Functions: `put_case(conn, case: dict, answers: dict)`, `get_case(conn, case_id) -> dict | None`, `get_answers(conn, case_id) -> dict`, `list_cases(conn, awaiting_approval: bool | None = None) -> list[dict]`, `add_approval(conn, case_id: str | None, txn_id: str | None, approver, approved: bool, at)`, `case_approval(conn, case_id) -> dict | None` (latest), `txn_pre_approved(conn, txn_id) -> bool`, `upsert_transactions(conn, rows: list[dict])` (`INSERT ... ON CONFLICT(txn_id) DO UPDATE`; when the stored row's columns differ from the incoming row, also `DELETE FROM verdicts WHERE txn_id = ?` so a changed memo, amount or `extraction_json` is re-decided; an identical row leaves its verdicts alone), `list_transactions(conn, company=None, limit=200, offset=0) -> list[dict]`, `count_transactions(conn, company=None) -> int`, `get_verdict(conn, txn_id, policy_version) -> dict | None`, `put_verdict(conn, txn_id, policy_version, case: dict)` (stores `case["verdict"]` in the column), `employee(conn, employee_id) -> dict | None`, `record_policy(conn, version, rules)`, `load_data_dir(conn, data_dir: str | None = None)` (`data_dir or os.environ.get("POP_DATA_DIR", "data")`, resolved inside the function for the same monkeypatch reason as `connect`).
- `load_data_dir` reads, when present: `employees.csv` (`employee_id,name,role,manager_id`, `INSERT OR REPLACE`), `approvals.csv` (`txn_id,approver,approved_at` → approvals rows with `approved=1`; first `DELETE FROM approvals WHERE case_id IS NULL` so a reload never duplicates file rows while `/approve` rows, which carry a `case_id`, survive), `transactions.csv` (`txn_id,company,employee_id,vendor,memo,amount,timestamp,qb_category,receipt_attached,receipt_date,source`), `extractions.jsonl` (`{"txn_id": ..., "facts": {...}}` → `transactions.extraction_json`). The demo employees `e_newhire/Sam Lee/employee/e_manager`, `e_intern/Ria Patel/intern/e_manager`, `e_contractor/Jo Kim/contractor/e_manager`, `e_manager/Dana Ortiz/employee/` are seeded by `init`, so `/check` works before B's file lands and in every test.

- [ ] **Step 1: Write the failing tests**

```python
def test_init_twice_and_seed_employees(tmp_path):
    conn = db.connect(tmp_path / "t.db"); db.init(conn); db.init(conn)
    db.load_data_dir(conn, tmp_path / "nodata")
    assert db.employee(conn, "e_intern")["role"] == "intern"

def test_load_data_dir_reads_b_files(tmp_path):
    (tmp_path / "transactions.csv").write_text("txn_id,company,employee_id,vendor,memo,amount,timestamp,qb_category,receipt_attached,receipt_date,source\n"
        "t1,demo,e_newhire,Uber,UBER TRIP,18.5,2026-09-30T08:10:00-07:00,Travel,1,2026-10-01,intuit\n")
    (tmp_path / "extractions.jsonl").write_text('{"txn_id": "t1", "facts": {"expense_kind": {"value": "rideshare", "p": 0.95}}}\n')
    (tmp_path / "approvals.csv").write_text("txn_id,approver,approved_at\nt1,e_manager,2026-09-29T10:00:00-07:00\n")
    conn = db.connect(tmp_path / "t.db"); db.init(conn); db.load_data_dir(conn, tmp_path)
    row = db.list_transactions(conn, company="demo")[0]
    assert row["amount"] == 18.5 and json.loads(row["extraction_json"])["expense_kind"]["value"] == "rideshare"
    assert db.txn_pre_approved(conn, "t1") is True and db.count_transactions(conn) == 1
```

- [ ] **Step 2: Run to verify it fails**  Expected: `ModuleNotFoundError: api.db`
- [ ] **Step 3: Implement `api/db.py`** with stdlib `sqlite3` and `csv`; `upsert` via `INSERT ... ON CONFLICT(txn_id) DO UPDATE`, preceded by a `SELECT` of the stored row to decide whether its verdicts are stale.
- [ ] **Step 4: Run tests**  Expected: PASS
- [ ] **Step 5: Commit**  `git commit -am "feat(api): sqlite schema and loaders for data files"`

---

### Task 7: Explanation and question templates

**Files:** Create `api/explain.py`; Test `api/test_explain.py`

**Interfaces:**
- Produces `QUESTION_TEXT: dict[str, str]` = `client_present: "Was a client present?"`, `at_company_event: "Was this at a company-wide event?"`, `receipt_attached: "Do you have the receipt?"`, `expense_kind: "What kind of expense is this?"`, `amount: "What is the amount in dollars?"`; `question(fact: str, p: float | None) -> dict` → `{"fact", "text", "p", "options"}` with `options` = the enum values for enum facts, else `None`.
- Produces `MERCHANT_CATEGORY: dict[str, str]` = `meal: "5812 Eating places"`, `rideshare: "4121 Taxicabs and rideshare"`, `airfare: "4511 Airlines"`, `hotel: "7011 Lodging"`, `software: "5734 Computer software"`, `equipment: "5045 Computers and peripherals"`, `entertainment: "7922 Entertainment"`, `other: "5999 Miscellaneous retail"`.
- Produces `phrase(fact: str, value) -> str`: `amount` → `"amount $48"` (`$48.50` when cents), `pre_approved False` → `"no pre-approval"`, `True` → `"pre-approved"`, `receipt_attached False` → `"no receipt"`, `coded_account v` → `"coded v"`, `at_company_event False` → `"not a company event"`, `client_present True` → `"client present"`, `role v` → `"role v"`, `expense_kind v` → `v`, `hour h` → `"at h:00"`, `days_since_purchase d` → `"d days ago"`.
- Produces `fix_phrase(step: FixStep) -> str`: `pre_approved → True` → `"get manager pre-approval"`, `receipt_attached → True` → `"attach the receipt"`, `coded_account → v` → `"code it as v"`, `amount → x` → `"keep it at or under $x"`.
- Produces `explain(decision, by_id: dict[str, Rule], unknown: list[str]) -> str`, joined with single spaces from these sentences, in this order:
  - per violation: `f"{rule.text.rstrip('.')} (rule {rule.id}): {', '.join(phrase(f, facts[f]) for f in because)}."`
  - fix: `"Fix: " + ", ".join(fix_phrase(s)) + "."`; `fix is None` → `"No change you control makes this compliant."`
  - compliant: `f"Compliant: rules {', '.join(applied)} hold."` (`"Compliant: no rule applies."` when empty)
  - undetermined: `f"Depends on: {QUESTION_TEXT[questions[0]]}"` if questions else `f"Depends on: {QUESTION_TEXT[unknown[0]]}"`
  - per derived fact: `f"Post it as {value} ({rule_id})."`

- [ ] **Step 1: Write the failing test**

```python
def test_dinner_explanation_is_templated():
    d = P.decide(UNCODED, {})
    assert explain(d, P.by_id, []) == ("Any expense over $35 needs manager pre-approval (rule 3.4): amount $48, no pre-approval. "
                                       "Fix: get manager pre-approval. Post it as meals_50 (IRS-meal).")
def test_question_for_enum_carries_options():
    assert question("expense_kind", None)["options"][0] == "meal"
```

- [ ] **Step 2: Run to verify it fails**  → **Step 3: Implement** → **Step 4: PASS** → **Step 5: Commit** `git commit -am "feat(api): templated explanations and question text"`

---

### Task 8: Real `/check`, `/cases`, `/answer`, `/approve`, `/authorize` (gate 20:00)

**Files:**
- Create: `api/cases.py`
- Modify: `api/routes_cases.py` (replace these six stubs), `api/main.py` (startup hook only), `api/conftest.py` (add the `fake_extractor` fixture)
- Test: `api/test_cases.py` (new; `api/test_api.py` stays the smoke test)

**Interfaces:**
- Consumes `Policy.decide`, `db.*`, `explain.*`. Imports Person B's `from extract.jev import extract` inside `try:`; on `ImportError` (or when `TYPESAFE_API_KEY` is unset) uses `engine.keyword_baseline.extract_stub` from Task 12 (if Task 12 is not merged yet, write the same regex table as `_fallback_extract` inside `cases.py` and swap it out when it is). Imports `from extract.mapping import coded_account_for` the same way; fallback maps `Meals`→`meals_50`, `Travel`→`travel`, `Office`→`office`, `Entertainment`→`entertainment_0`, else `other`.
- Consumes (Task 12 produces it) `keyword_baseline.extract_stub(text: str) -> dict[str, dict]` in the `extract()` shape: regex table `dinner|lunch|meal|restaurant|coffee` → meal, `uber|lyft|taxi|ride` → rideshare, `flight|airfare|airline` → airfare, `hotel|lodging|airbnb` → hotel, `subscription|saas|license|software` → software, `laptop|monitor|keyboard|equipment` → equipment, `tickets|concert|game|show` → entertainment, else other; matched → `p 0.9`, else `p 0.5`; `client_present` p `0.9` when `client|customer|cfo|ceo|prospect` else `0.5`; `at_company_event` p `0.9` when `offsite|all-hands|company event|team event` else `0.1`.
- Produces in `cases.py`:
  - `POLICY: Policy` loaded once at import from both packs; `now_la() -> datetime`.
  - `parse_amount(text: str) -> float | None` using `re.search(r"\$\s*(\d+(?:\.\d{1,2})?)", text)`.
  - `parse_ts(s: str | None) -> tuple[datetime, bool]` (ISO; naive → `ZoneInfo("America/Los_Angeles")`; `None` → `(now, True)`; the bool is `has_time = len(s.strip()) > 10`, false for a date-only string like `2026-09-30`).
  - `build_facts(text, employee: dict, amount, ts, has_time, answers: dict, approved: bool | None) -> tuple[dict, dict, dict]` → `(facts, probs, sources)`: `role` from the employee record (`employee`); `amount` from the body (`user`) else `parse_amount` (`text`); `hour` only when `has_time`, `days_since_purchase = max(0, (now - ts).days)` (`derived`); `pre_approved = bool(approved)` (`approvals`); extractor facts via `facts_from_probs` (`jev`); `answers` override anything (`answer`). Every engine call (`POLICY.decide`) already runs under `ENGINE_LOCK`; `cases.py` adds no lock of its own.
  - `to_case(case_id, created_at, employee_id, text, decision, sources, probs, approval, authorization) -> dict` (the `Case` shape; `facts[name] = {"value", "source", "p"}` with `source "rules"` for derived; `awaiting_approval = verdict == "violation" and any(step.fact == "pre_approved" for step in fix or []) and approval is None`; if `undetermined` and `questions` empty, append `question(f)` for the first of `expense_kind`, `amount` that is unknown).
  - `new_case(conn, req: CheckRequest) -> dict` (`case_id = "c_" + secrets.token_hex(4)`; 404 if the employee is unknown; `CheckRequest.amount` is `Field(None, gt=0)` so a refund or zero never reaches the solver), `rerun(conn, case_id) -> dict`, `answer(conn, case_id, fact, value) -> dict` (422 if `fact == "pre_approved"` or `schema.validate_value(fact, value)` raises `KeyError` or `ValueError`; store the coerced value), `approve(conn, case_id, approver, approved) -> dict`, `authorize(conn, case_id) -> dict` (409 `"not compliant"` unless `compliant`; 409 `"amount unknown"` when `amount` is not in `facts`, which a compliant case can reach once pre-approval and a receipt are set with the price never given; idempotent; `auth_id = "auth_" + token_hex(4)`, `amount_limit = facts["amount"]`, `merchant_category = MERCHANT_CATEGORY[expense_kind]`, `expires_at = now + 24h`, `proof_hash`; also `upsert_transactions` one row with `txn_id = case_id`, `company "demo"`, `source "case"`, `coded_account = facts["coded_account"]`).
  - `proof_hash(fact_values: dict, policy_version: str, verdict: str) -> str`.
  - Consumes `engine.keyword_baseline.txn_row` (Task 12) to normalize a ledger row; same interim rule as for `extract_stub`: if Task 12 is not merged yet, write it as `_txn_row` inside `cases.py` and swap it out when it is.
  - `decide_transaction(txn: dict, extraction: dict | None, pre_approved: bool, employee: dict | None) -> dict` → case-shaped dict for a ledger row, after `txn = txn_row(txn)` (`days_since_purchase` = `receipt_date - timestamp` when a receipt is attached, else `now - timestamp`; `hour` only when the timestamp has a time part; `coded_account = coded_account_for(qb_category)`; `receipt_attached` from the row, absent when `None`). Person B's `eval/run.py` imports this one function so the evaluation runs the exact production pipeline.
- `main.py` startup: `db.load_data_dir(conn)` and `db.record_policy` on a connection it closes again (`init` runs inside `connect`). `routes_cases.py` opens a connection per request and calls `cases.*`; HTTPException codes as above; these six routes drop the `X-Stub` header.

- [ ] **Step 1: Write the failing tests** (replace the stub expectations for these routes; keep the stub tests for the others)

```python
# in api/conftest.py (Task 1 created it):
@pytest.fixture(autouse=True)
def fake_extractor(monkeypatch):
    from api import cases
    monkeypatch.setattr(cases, "extract", lambda text: {"expense_kind": {"value": "meal", "p": 0.97},
        "client_present": {"p": 0.91}, "at_company_event": {"p": 0.08}})

# api/test_cases.py
TS = datetime.now(ZoneInfo("America/Los_Angeles")).replace(hour=19, minute=30).isoformat()
# today at 19:30: hour is fixed so rules 6.1/6.2 never depend on when the suite runs, and days_since_purchase
# stays 0 so rule 4.1 (receipt due after 14 days) never wakes up on a later date. Every /check below passes TS.

def test_demo_flow_check_approve_authorize(client):
    c = client.post("/check", json={"text": "Client dinner Thursday with Acme's CFO, about $48.", "employee_id": "e_newhire", "timestamp": TS}).json()
    assert c["verdict"] == "violation" and [v["rule"] for v in c["violations"]] == ["3.4"]
    assert c["facts"]["coded_account"] == {"value": "meals_50", "source": "rules", "p": None}
    assert c["facts"]["amount"]["source"] == "text" and c["awaiting_approval"] is True
    assert client.get("/cases", params={"awaiting_approval": "true"}).json()["cases"][0]["case_id"] == c["case_id"]
    assert client.post(f"/cases/{c['case_id']}/authorize").status_code == 409
    a = client.post(f"/cases/{c['case_id']}/approve", json={"approver": "e_manager", "approved": True}).json()
    assert a["verdict"] == "compliant" and a["awaiting_approval"] is False and a["approval"]["approver"] == "e_manager"
    auth = client.post(f"/cases/{c['case_id']}/authorize").json()
    assert auth["amount_limit"] == 48 and auth["merchant_category"] == "5812 Eating places" and len(auth["proof_hash"]) == 64
    assert client.post(f"/cases/{c['case_id']}/authorize").json()["auth_id"] == auth["auth_id"]
    assert client.get(f"/cases/{c['case_id']}").json()["authorization"]["auth_id"] == auth["auth_id"]
    assert client.get("/cases", params={"awaiting_approval": "true"}).json()["cases"] == []

def test_answer_settles_an_undetermined_case(client, monkeypatch):
    monkeypatch.setattr(cases, "extract", lambda t: {"expense_kind": {"value": "rideshare", "p": 0.95}, "at_company_event": {"p": 0.5}})
    c = client.post("/check", json={"text": "Lyft to the offsite", "employee_id": "e_intern", "amount": 20, "timestamp": TS}).json()
    assert c["verdict"] == "undetermined" and c["questions"][0]["fact"] == "at_company_event"
    a = client.post(f"/cases/{c['case_id']}/answer", json={"fact": "at_company_event", "value": True}).json()
    assert a["verdict"] == "compliant" and a["facts"]["at_company_event"]["source"] == "answer"

def test_review_focus_edges(client):
    assert client.post("/check", json={"text": "dinner", "employee_id": "nobody", "timestamp": TS}).status_code == 404
    assert client.post("/check", json={"text": "dinner", "employee_id": "e_newhire", "amount": -5, "timestamp": TS}).status_code == 422
    c = client.post("/check", json={"text": "Team dinner, not sure of the price", "employee_id": "e_newhire", "timestamp": TS}).json()
    assert c["verdict"] == "undetermined" and c["questions"][0]["fact"] == "amount" and "amount" in c["explanation"].lower()
    cid = c["case_id"]
    for bad in [{"fact": "colour", "value": True}, {"fact": "pre_approved", "value": True}, {"fact": "at_company_event", "value": "yes"},
                {"fact": "amount", "value": -1}, {"fact": "hour", "value": 99}, {"fact": "expense_kind", "value": "snack"}]:
        assert client.post(f"/cases/{cid}/answer", json=bad).status_code == 422, bad

def test_authorize_needs_a_known_amount(client):
    # compliant with the price never given: approve, then attach the receipt; the card still cannot be issued
    c = client.post("/check", json={"text": "Team dinner, not sure of the price", "employee_id": "e_newhire", "timestamp": TS}).json()
    client.post(f"/cases/{c['case_id']}/approve", json={"approver": "e_manager", "approved": True})
    a = client.post(f"/cases/{c['case_id']}/answer", json={"fact": "receipt_attached", "value": True}).json()
    assert a["verdict"] == "compliant" and "amount" not in a["facts"]
    r = client.post(f"/cases/{c['case_id']}/authorize")
    assert r.status_code == 409 and r.json()["detail"] == "amount unknown"

def test_date_only_timestamp_leaves_hour_unknown(client):
    c = client.post("/check", json={"text": "Team dinner $20", "employee_id": "e_newhire", "timestamp": TS[:10]}).json()
    assert "hour" not in c["facts"]
    assert c["verdict"] == "undetermined"   # a $20 meal is fine at 19:00 and needs approval at 23:00; with the hour free the solver cannot decide
```

- [ ] **Step 2: Run to verify it fails**  Expected: FAIL (stub returns the sample case; no `cases` module)
- [ ] **Step 3: Write `api/cases.py`** as pinned.
- [ ] **Step 4: Replace the six stubs in `api/routes_cases.py`**; add the startup hook to `main.py`; `GET /health` now reports the real `policy_version` and `stub: false` once no stub route remains (keep `true` until Task 12).
- [ ] **Step 5: Run tests**  Run: `pytest -q`  Expected: PASS
- [ ] **Step 6: Run it for real**: `uvicorn api.main:app --reload --port 8000`, then the demo `curl` from the README; paste the case JSON into team chat so B and C see real output.
- [ ] **Step 7: Commit and push**  `git commit -am "feat(api): real check, answer, approve, authorize with proof hash" && git push`

---

### Task 9: Ledger and the cached audit (gate 02:00)

**Files:** Create `api/ledger.py`; Modify `api/routes_ledger.py`; Test `api/test_ledger.py`

**Interfaces:**
- Consumes `cases.decide_transaction`, `db.*`.
- Produces `ledger.row_case(conn, txn: dict, policy_version: str) -> dict`: returns `db.get_verdict` if cached, else runs `decide_transaction` (extraction from `txn["extraction_json"]`, `pre_approved = db.txn_pre_approved`, employee from `db.employee`) and `db.put_verdict`. A failure on one row is caught and recorded as `undetermined` with `explanation "Could not evaluate: <error>"` (`# ponytail: never let one bad row kill the audit`).
- Produces `ledger.rows(conn, company, verdict, limit, offset, policy_version) -> tuple[list[dict], int]` → `LedgerRow` dicts (`violations` = rule ids, `case` = the case dict) and the total. It first makes sure every transaction in scope has a verdict row for this `policy_version` (`row_case` on the missing ones), then filters and counts on the `verdicts.verdict` column in SQL; `total` is the count after the verdict filter.
- Produces `ledger.audit(conn, company, policy, by_id) -> dict` → `AuditSummary`: `by_verdict` counts, `by_rule` sorted by count desc, `top_violations` = first 20 violation rows, `elapsed_ms`.
- Routes: `GET /ledger`, `POST /ledger/audit` drop `X-Stub`.

- [ ] **Step 1: Write the failing test**

```python
def test_ledger_audit_counts_and_caches(client):
    conn = db.connect()   # POP_DB is set by the client fixture in api/conftest.py
    db.upsert_transactions(conn, [
      dict(txn_id="t1", company="demo", employee_id="e_newhire", vendor="Uber", memo="UBER TRIP", amount=18.5, timestamp="2026-09-30T08:10:00-07:00", qb_category="Travel", receipt_attached=1, receipt_date="2026-10-01", source="intuit", extraction_json=json.dumps({"expense_kind": {"value": "rideshare", "p": 0.95}})),
      dict(txn_id="t2", company="demo", employee_id="e_newhire", vendor="Nobu", memo="NOBU LA", amount=120, timestamp="2026-09-20T20:30:00-07:00", qb_category="Travel", receipt_attached=1, receipt_date="2026-09-21", source="injected", extraction_json=json.dumps({"expense_kind": {"value": "meal", "p": 0.96}, "client_present": {"p": 0.9}, "at_company_event": {"p": 0.05}})),
      dict(txn_id="t3", company="demo", employee_id="e_newhire", vendor="?", memo="MISC", amount=12, timestamp="2026-09-25T12:00:00-07:00", qb_category="Other", receipt_attached=1, receipt_date="2026-09-25", source="intuit", extraction_json=None)])
    a = client.post("/ledger/audit", json={"company": "demo"}).json()
    assert a["n"] == 3 and a["by_verdict"] == {"compliant": 1, "violation": 1, "undetermined": 1}
    assert {r["rule"] for r in a["by_rule"]} == {"3.4", "IRS-meal"}
    assert conn.execute("select count(*) from verdicts").fetchone()[0] == 3
    assert client.get("/ledger", params={"company": "demo", "verdict": "violation"}).json()["transactions"][0]["txn_id"] == "t2"
```

- [ ] **Step 2: Run to verify it fails** → **Step 3: Implement `api/ledger.py`** and the two routes → **Step 4: PASS**
- [ ] **Step 5: Time it**: load B's `data/transactions.csv` and `extractions.jsonl`, run `POST /ledger/audit` once cold. With Task 3's joint-first check the measured cost is ~1.5 ms per compliant row (about 2 s for 1,240 rows, plus the per-rule cores on violations and `questions` on undetermined rows). If `elapsed_ms` is still > 5000, the next step is one `Solver` with `push()`/`pop()` per transaction (the spec's escape hatch), and only after that any change to what `decide` computes for ledger rows.
- [ ] **Step 6: Commit and push**  `git commit -am "feat(api): ledger rows and cached audit per policy version"`

---

### Task 10: Full demo policy, IRS pack, a test per rule, `/policy` and `/policy/audit`

**Files:** Modify `engine/demo_policy.json`, `engine/irs_pack.json`, `engine/rules.py` (`audit`, `disagreement`, `facts_from_model`), `api/routes_policy.py`; Test `engine/test_policy_packs.py`, `api/test_policy.py`

**Interfaces:**
- Produces `Policy.facts_from_model(model: z3.ModelRef) -> dict[str, object]` (every fact, via `model.eval(var, model_completion=True)` and `from_z3`).
- Produces `Policy.audit() -> dict` = `{"dead": [rule ids where unsat(dom, when)], "conflicts": [{"a", "b", "example": facts} for pairs i < j where both apply and each can be met on its own but not together]}`. Pinned, with `both = dom + [when_a, when_b]`: skip the pair when `unsat(both)`; skip it when `unsat(both, require_a)` or `unsat(both, require_b)` (a prohibition such as 5.1 or 6.4, `require: false`, is never "in conflict" with a rule that says "only with approval"; without this exclusion the shipped pack reports 18 bogus conflicts, every one of them involving 5.1 or 6.4); report it when `unsat(both, require_a, require_b)`, with `example = facts_from_model` of the model for `both`. Verified against the full pack: zero conflicts, and the injected X/Y test below returns exactly `{("X", "Y")}`.
- Known limit, note it in `README.md`: `days_since_purchase` for a ledger row with a receipt is `receipt_date - timestamp`, so a receipt filed on day 75 satisfies IRS-receipt-60; the rules catch a receipt that is *missing* after the deadline (the evaluation's injected case), not one that arrived late.
- Produces `Policy.disagreement(rule_a: dict, rule_b: dict) -> dict | None`: compile both; `sat(dom, formula_a != formula_b)` → `facts_from_model`, else `None`.
- Rules (ids are referenced by tests and explanations; `text` is what the dashboard shows):

| id | layer | text | when | require |
| --- | --- | --- | --- | --- |
| 3.4 | company | Any expense over $35 needs manager pre-approval. | gt amount 35 | pre_approved |
| 3.5 | company | Any expense over $500 needs a receipt attached. | gt amount 500 | receipt_attached |
| 4.1 | company | Receipts for expenses over $25 are due within 14 days. | and(gt amount 25, gt days_since_purchase 14) | receipt_attached |
| 5.1 | company | Contractors are not reimbursed for meals. | and(eq role contractor, eq expense_kind meal) | false |
| 5.2 | company | Interns get no transport reimbursement except at company events. | and(eq role intern, in expense_kind [rideshare, airfare]) | at_company_event |
| 5.3 | company | Interns may expense meals only at company events. | and(eq role intern, eq expense_kind meal) | at_company_event |
| 6.1 | company | Meals after 10pm need pre-approval. | and(eq expense_kind meal, ge hour 22) | pre_approved |
| 6.2 | company | Meals before 6am need pre-approval. | and(eq expense_kind meal, lt hour 6) | pre_approved |
| 6.3 | company | Entertainment always needs pre-approval. | eq expense_kind entertainment | pre_approved |
| 6.4 | company | Entertainment over $100 is never reimbursed. | and(eq expense_kind entertainment, gt amount 100) | false |
| 6.5 | company | Client meals over $150 need pre-approval even with a client present. | and(eq expense_kind meal, eq client_present true, gt amount 150) | pre_approved |
| 7.1 | company | Airfare always needs pre-approval. | eq expense_kind airfare | pre_approved |
| 7.2 | company | Hotels over $300 a night need pre-approval. | and(eq expense_kind hotel, gt amount 300) | pre_approved |
| 8.1 | company | Software needs IT pre-approval at any price. | eq expense_kind software | pre_approved |
| 8.2 | company | Equipment over $250 needs pre-approval and a receipt. | and(eq expense_kind equipment, gt amount 250) | and(pre_approved, receipt_attached) |
| 9.1 | company | Rideshare over $75 needs pre-approval. | and(eq expense_kind rideshare, gt amount 75) | pre_approved |
| IRS-meal | irs | Business meals outside company-wide events are 50% deductible. | and(eq expense_kind meal, not at_company_event) | eq coded_account meals_50 |
| IRS-meal-event | irs | Meals at company-wide events are 100% deductible. | and(eq expense_kind meal, at_company_event) | eq coded_account meals_100 |
| IRS-ent | irs | Entertainment is not deductible. | eq expense_kind entertainment | eq coded_account entertainment_0 |
| IRS-travel | irs | Rideshare, airfare and hotels are travel. | in expense_kind [rideshare, airfare, hotel] | eq coded_account travel |
| IRS-office | irs | Software and equipment are office expenses. | in expense_kind [software, equipment] | eq coded_account office |
| IRS-other | irs | Anything else is coded other. | eq expense_kind other | eq coded_account other |
| IRS-receipt-60 | irs | Receipts must be substantiated within 60 days of the expense. | gt days_since_purchase 60 | receipt_attached |
| IRS-receipt-75 | irs | Expenses of $75 or more need a receipt. | and(ge amount 75, gt days_since_purchase 0) | receipt_attached |

- [ ] **Step 1: Write the failing tests**

```python
# engine/test_policy_packs.py: one (rule_id, breaking_facts, passing_facts) row per rule above, e.g.
CASES = [
  ("3.4", dict(BASE, amount=36, pre_approved=False), dict(BASE, amount=35, pre_approved=False)),
  ("6.4", dict(BASE, expense_kind="entertainment", amount=101, pre_approved=True, coded_account="entertainment_0"), dict(BASE, expense_kind="entertainment", amount=100, pre_approved=True, coded_account="entertainment_0")),
  ("IRS-receipt-60", dict(BASE, days_since_purchase=75, receipt_attached=False, amount=20), dict(BASE, days_since_purchase=75, receipt_attached=True, amount=20)),
  # ... every id in the table
]
@pytest.mark.parametrize("rule_id,breaking,passing", CASES)
def test_each_rule_bites_and_releases(rule_id, breaking, passing):
    assert rule_id in {v.rule for v in P.check(breaking).violations}
    assert rule_id not in {v.rule for v in P.check(passing).violations}

def test_every_rule_has_a_case():
    assert {c[0] for c in CASES} == set(P.by_id)

def test_demo_policy_has_no_dead_rules_or_conflicts():
    assert P.audit() == {"dead": [], "conflicts": []}

def test_audit_finds_an_injected_dead_rule_and_conflict():
    q = Policy(P_RAW + [
      {"id": "D", "layer": "company", "text": "t", "when": {"and": [{"eq": ["role", "intern"]}, {"eq": ["role", "employee"]}]}, "require": "pre_approved"},
      {"id": "X", "layer": "company", "text": "t", "when": {"eq": ["role", "intern"]}, "require": {"eq": ["expense_kind", "meal"]}},
      {"id": "Y", "layer": "company", "text": "t", "when": {"eq": ["role", "intern"]}, "require": {"neq": ["expense_kind", "meal"]}}])
    a = q.audit()
    assert a["dead"] == ["D"] and {(c["a"], c["b"]) for c in a["conflicts"]} == {("X", "Y")} and a["conflicts"][0]["example"]["role"] == "intern"

def test_over_35_disagreement_is_exactly_35():
    ge = {**P.by_id["3.4"].raw, "when": {"ge": ["amount", 35]}}
    ex = P.disagreement(P.by_id["3.4"].raw, ge)
    assert ex["amount"] == 35.0 and ex["pre_approved"] is False
```

`BASE = dict(role="employee", expense_kind="meal", client_present=False, at_company_event=False, amount=20, hour=12, days_since_purchase=0, receipt_attached=True, pre_approved=True, coded_account="meals_50")`.

- [ ] **Step 2: Run to verify it fails** → **Step 3: Write both JSON packs and the three engine methods** → **Step 4: `pytest -q engine/` PASS**
- [ ] **Step 5: Routes**: `GET /policy` → `{version, rules: [r.raw], facts: {name: FactSpec._asdict()}}`; `POST /policy/audit` → `Policy.audit()`; both drop `X-Stub`. Test: `client.get("/policy").json()["rules"]` has 24 entries; `/policy/audit` returns empty lists.
- [ ] **Step 6: Commit and push**  `git commit -am "feat(engine): full company + IRS packs, per-rule tests, policy audit"`

---

### Task 11: Bank-rule checker and `/bank-rules/check`

**Files:** Create `engine/bank_rules.py`; Modify `api/routes_bank.py`; Test `engine/test_bank_rules.py`, `api/test_bank.py`

**Interfaces:**
- Produces `check_bank_rules(rules: list[dict]) -> dict` with input rows `{"id", "contains": [str], "amount_min"?: float, "amount_max"?: float, "category"}` (first match wins by list order) and output `{"shadowed": [{"rule": id, "by": [earlier ids]}], "overlaps": [{"a": id, "b": id, "example": {"description": str, "amount": float}}]}`.
- Pinned: `d = z3.String("description"); amt = z3.Real("amount")`; `match_i = And(*[Contains(d, StringVal(w.upper())) for w in contains], amt >= min, amt <= max)` (bounds only when given). Rule `j` is shadowed when `unsat(match_j, Not(Or(*match_i for i < j)))`; `by` = each earlier `i` with `unsat(match_j, Not(match_i))`. Pair `i < j` with different `category` overlaps when `sat(match_i, match_j)`; `example` from the model (`model[d].as_string()`, `float(model[amt].as_fraction())`). Noisy-overlap filter (the spec's): keep an overlap only when every word of one rule is a substring of some word of the other.

- [ ] **Step 1: Write the failing tests**

```python
def test_uber_eats_after_uber_is_shadowed():
    out = check_bank_rules([{"id": "r1", "contains": ["UBER"], "category": "Travel"}, {"id": "r2", "contains": ["UBER", "EATS"], "category": "Meals"}])
    assert out["shadowed"] == [{"rule": "r2", "by": ["r1"]}]

def test_uber_eats_before_uber_overlaps_with_an_example():
    out = check_bank_rules([{"id": "r1", "contains": ["UBER", "EATS"], "category": "Meals"}, {"id": "r2", "contains": ["UBER"], "category": "Travel"}])
    assert out["shadowed"] == [] and out["overlaps"][0]["a"] == "r1" and "UBER" in out["overlaps"][0]["example"]["description"]

def test_unrelated_words_are_filtered_as_noise():
    out = check_bank_rules([{"id": "r1", "contains": ["UBER"], "category": "Travel"}, {"id": "r2", "contains": ["AMAZON"], "category": "Office"}])
    assert out["overlaps"] == []

def test_disjoint_amount_ranges_do_not_overlap():
    out = check_bank_rules([{"id": "r1", "contains": ["STARBUCKS"], "amount_max": 20, "category": "Meals"}, {"id": "r2", "contains": ["STARBUCKS"], "amount_min": 20.01, "category": "Office"}])
    assert out["overlaps"] == [] and out["shadowed"] == []
```

- [ ] **Step 2: Run to verify it fails** → **Step 3: Implement** → **Step 4: PASS**
- [ ] **Step 5: Route** `POST /bank-rules/check` → `check_bank_rules([r.model_dump() for r in body.rules])`, drop `X-Stub`; test with the shadowed pair through the client.
- [ ] **Step 6: Commit and push**  `git commit -am "feat(engine): bank-rule shadow/overlap checker with Z3 strings"`

---

### Task 12: Keyword baseline and `/eval`

**Files:** Create `engine/keyword_baseline.py`; Modify `api/routes_eval.py`; Test `engine/test_keyword_baseline.py`, `api/test_eval.py`

**Interfaces:**
- Produces `extract_stub(text: str) -> dict[str, dict]` exactly as specified in Task 8's Interfaces (the regex table lives there), `CODED_FALLBACK: dict[str, str]` (`Meals`→`meals_50`, `Travel`→`travel`, `Office`→`office`, `Entertainment`→`entertainment_0`, else `other`; `cases.py` imports this instead of keeping its own copy), `txn_row(txn: dict) -> dict` (normalizes **one `transactions.csv` row as a dict, every value a string**, which is what the contract tells B to pass, or a typed DB row with `NULL`s, to one shape: `amount` → `float`; `receipt_attached` `""`/`None` → `None`, `"1"`/`1`/`"true"` → `True`, `"0"`/`0`/`"false"` → `False`; `receipt_date`, `employee_id`, `qb_category` `""` → `None`; lives in `engine/` because `api/cases.py` imports it and engine never imports api), and `keyword_verdict(txn: dict, pre_approved: bool = False) -> dict` = `{"verdict": "compliant"|"violation", "rules": [ids]}` with no Z3: `t = txn_row(txn)`; `receipt = t["receipt_attached"] is True`; `days = (date(receipt_date) - date(timestamp)).days if receipt else (today - date(timestamp)).days`; `coded = CODED_FALLBACK.get(t["qb_category"], "other")`; `kind = extract_stub(t["memo"])["expense_kind"]["value"]` and a literal list of `(rule_id, predicate)` lambdas mirroring the amount thresholds in Task 10's table (`3.4: amount > 35 and not pre_approved`, `6.4: kind == entertainment and amount > 100`, `IRS-receipt-60: days > 60 and not receipt`, `IRS-meal: kind == meal and coded != meals_50`, …). It never says `undetermined`; that is the point of the baseline. Person B's `eval/run.py` imports it and passes `pre_approved` from `approvals.csv` (the one-argument call in the contract still works and means "no pre-approval").
- `GET /eval`: read `eval/results.json` if it exists and return it as-is (validated by `EvalOut`), dropping `X-Stub`; otherwise return `{"as_of": null, "n_heldout": 0, "systems": []}` with `X-Stub: 1`. `GET /health` reports `stub: false` once `eval/results.json` exists.

- [ ] **Step 1: Write the failing tests**

```python
ROW = dict(txn_id="t1", company="demo", employee_id="e_newhire", vendor="Uber", memo="UBER TRIP", amount="18.5",
           timestamp="2026-09-30T08:10:00-07:00", qb_category="Travel", receipt_attached="1", receipt_date="2026-10-01", source="intuit")
def test_keyword_verdict_takes_a_raw_csv_row():
    assert keyword_verdict(ROW)["verdict"] == "compliant"
    nobu = {**ROW, "memo": "NOBU LA dinner", "amount": "210", "timestamp": "2026-09-20T20:30:00-07:00", "receipt_date": "2026-09-21"}
    assert {"3.4", "IRS-meal"} <= set(keyword_verdict(nobu)["rules"])
    assert "3.4" not in keyword_verdict(nobu, pre_approved=True)["rules"]
def test_eval_serves_results_file(client, tmp_path, monkeypatch):
    monkeypatch.setattr(routes_eval, "EVAL_RESULTS", tmp_path / "results.json")
    assert client.get("/eval").headers.get("x-stub") == "1"
    (tmp_path / "results.json").write_text(json.dumps(samples.SAMPLE_EVAL))
    r = client.get("/eval"); assert r.headers.get("x-stub") is None and r.json()["systems"][0]["name"]
```

- [ ] **Step 2–4: fail → implement → PASS**
- [ ] **Step 5: Commit and push**  `git commit -am "feat: keyword baseline and /eval from results.json"`

---

### Task 13 (stretch, only after the 02:00 gate): what-if

**Files:** Modify `api/routes_policy.py`, `api/ledger.py`; Test `api/test_policy.py`

- `POST /policy/what-if` body `{"rule": <rule JSON>}` → replaces the rule with the same `id` (or appends) in a throwaway `Policy`, re-runs `decide_transaction` over the company's transactions, returns `{"policy_version": new, "flipped": [{"txn_id", "from", "to"}], "n": int}`. Test: tighten `3.4` to `gt amount 15` on the three ledger rows → `t1` flips `compliant → violation`.
- Commit: `git commit -am "feat(api): what-if re-audit with one edited rule"`

---

### Task 14: Data reload and real-data hardening (Intuit ledger refreshes)

**Files:** Modify `api/db.py`, `api/cases.py` (`decide_transaction` only), `api/routes_ledger.py`; Test `api/test_db.py`, `api/test_ledger.py`

**Interfaces:**
- Consumes `db.load_data_dir` (Task 6; reads `POP_DATA_DIR` at call time), `ledger.audit` (Task 9).
- `db.load_data_dir(conn, data_dir=None) -> dict` now returns `{"transactions": int, "employees": int, "extractions": int, "approvals": int, "skipped": [{"txn_id": str, "reason": str}]}` and applies, per `transactions.csv` row: `amount` missing, non-numeric or `<= 0` → skipped, reason `"amount must be > 0 (refunds and credits are not audited)"`; `timestamp` unparsable → skipped, reason `"bad timestamp"`; blank `receipt_attached` → stored `NULL` (unknown, never `0`); blank `employee_id` → `NULL` (role unknown); a `txn_id` already stored under a different `company` → skipped, reason `"txn_id collision"`.
- `cases.decide_transaction`: `receipt_attached is None` → the fact is absent from `facts`.
- `POST /data/reload` in `routes_ledger.py` → calls `load_data_dir(conn)` (no path argument, so the env override applies) and returns its dict. The next `POST /ledger/audit` decides only rows with no cached verdict for the current `policy_version` (Task 9's cache already does this), so a reload is incremental; a rule change invalidates everything by changing `policy_version`, and a changed row (new memo, amount or extraction) drops only its own verdicts in `upsert_transactions` (Task 6).
- Periodic refresh is on Person B's side and needs no API change: run `data/load_intuit.py` on a loop or cron, then `curl -X POST $API_URL/data/reload`. A live QuickBooks Online pull, if B gets to it, writes the same `transactions.csv`.

- [ ] **Step 1: Write the failing tests**

```python
HEADER = "txn_id,company,employee_id,vendor,memo,amount,timestamp,qb_category,receipt_attached,receipt_date,source\n"

def test_reload_skips_refunds_and_keeps_blank_receipt_unknown(client, tmp_path, monkeypatch):
    monkeypatch.setenv("POP_DATA_DIR", str(tmp_path)); conn = db.connect()
    (tmp_path / "transactions.csv").write_text(HEADER
        + "t1,demo,e_newhire,Uber,UBER TRIP,18.5,2026-09-30T08:10:00-07:00,Travel,,2026-10-01,intuit\n"
        + "t2,demo,e_newhire,Uber,UBER REFUND,-18.5,2026-10-02T08:10:00-07:00,Travel,1,,intuit\n")
    r = client.post("/data/reload").json()
    assert r["transactions"] == 1
    assert r["skipped"] == [{"txn_id": "t2", "reason": "amount must be > 0 (refunds and credits are not audited)"}]
    row = db.list_transactions(conn, company="demo")[0]
    assert row["receipt_attached"] is None
    assert "receipt_attached" not in cases.decide_transaction(row, None, False, db.employee(conn, "e_newhire"))["facts"]

def test_reload_then_audit_is_incremental(client, tmp_path, monkeypatch):
    monkeypatch.setenv("POP_DATA_DIR", str(tmp_path)); conn = db.connect()
    T1 = "t1,demo,e_newhire,Uber,UBER TRIP,18.5,2026-09-30T08:10:00-07:00,Travel,1,2026-10-01,intuit\n"
    (tmp_path / "transactions.csv").write_text(HEADER + T1)
    client.post("/data/reload"); client.post("/ledger/audit", json={"company": "demo"})
    first = conn.execute("select case_json from verdicts where txn_id='t1'").fetchone()[0]
    with open(tmp_path / "transactions.csv", "a") as f:
        f.write("t3,demo,e_newhire,Nobu,NOBU LA,120,2026-09-20T20:30:00-07:00,Travel,1,2026-09-21,injected\n")
    assert client.post("/data/reload").json()["transactions"] == 2
    a = client.post("/ledger/audit", json={"company": "demo"}).json()
    assert a["n"] == 2 and conn.execute("select count(*) from verdicts").fetchone()[0] == 2
    assert conn.execute("select case_json from verdicts where txn_id='t1'").fetchone()[0] == first   # unchanged row, untouched verdict
    (tmp_path / "transactions.csv").write_text(HEADER + T1.replace("18.5", "95"))                  # changed row, verdict dropped
    client.post("/data/reload")
    assert conn.execute("select count(*) from verdicts where txn_id='t1'").fetchone()[0] == 0
    assert client.post("/ledger/audit", json={"company": "demo"}).json()["by_verdict"]["violation"] == 2   # 95 > 35, no pre-approval
```

- [ ] **Step 2: Run to verify it fails** → **Step 3: Implement** the loader rules, the `None` receipt path and the route → **Step 4: PASS**
- [ ] **Step 5: Commit and push**  `git commit -am "feat(api): /data/reload with incremental audit and refund/blank-cell handling"`

---

## Parallel execution

The streams, ownership and gates for running Tasks 2 to 14 with several workers at once are in `docs/superpowers/plans/2026-10-17-parallel-execution-prompt.md`; paste that file into a fresh session as the orchestrator's prompt.

## Hand-offs during the day

- **15:00** (after Task 1): push; tell C "stub API is on `main`, deploy it"; send B the contract doc link.
- **With B, before Task 9**: agree on `extract/mapping.py:coded_account_for` outputs for every QuickBooks category in `data/SCHEMA.md`; it must return one of the six `coded_account` values.
- **20:00** (after Task 8): paste a real `/check` → `/approve` → `/authorize` transcript in team chat.
- **02:00** (after Tasks 9–11): run `POST /ledger/audit` on B's full ledger, report `elapsed_ms` and the counts; B starts `eval/run.py` against `cases.decide_transaction` and `keyword_verdict`.
- **Cut order if behind** (from the spec): Task 13 first, then the bank-rule page (keep Task 11's API), then the approvals tab (set `pre_approved` through `/approve` by hand in the demo). Never cut Tasks 8, 9, 12.
