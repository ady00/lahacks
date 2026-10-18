# Data, policy scenarios, and evaluation

Person B's reusable services live in `jev_z3/backend`. They run without FastAPI, credentials, or model access. The existing `jev-z3` CLI and Person A's `engine`/`api` modules retain their behavior.

## Reproduce the build

From the repository root, with Python 3.10+ (3.11 recommended):

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e '.[dev]'
.venv\Scripts\python.exe -m jev_z3.backend.cli build
.venv\Scripts\python.exe -m jev_z3.backend.cli evaluate
.venv\Scripts\python.exe -m jev_z3.backend.cli audit --cases artifacts/backend/demo_ledger.jsonl
.venv\Scripts\python.exe -m pytest -q
```

After activating the environment, `purchase-backend` is the equivalent entry point. On macOS/Linux use `.venv/bin/python`.

The archive must already exist at `data/hackathon-100-participant.tar.gz`, or pass `--archive PATH`. Source: [QuickBooks Hackathon dataset](https://huggingface.co/datasets/CL251215/QuickBooks-Hackathon-2026/tree/main). The validated archive SHA-256 is `6090485212458315c6d58c2793221b79de54fa89191edccaeba2c5c1c5cb1f38`. Commands never alter or extract it.

`build` reads and validates all 100 companies, writes 36,032 bank-linked purchase cases, creates 200 evaluation cases, and exports the selected policy. Default demo company: `company-072` (31 purchases). Build artifacts are ignored by Git and reproducible:

| Artifact under `artifacts/backend/` | Contents |
| --- | --- |
| `ledger/purchases.jsonl` | One normalized purchase per settled/partially settled bill across all companies |
| `ledger/employees.jsonl` | Source employees, company-scoped IDs, unknown policy roles |
| `ledger/manifest.json` | Archive hash, per-company validation counts and exclusions |
| `demo_ledger.jsonl` | Selected demo company's purchases |
| `fixtures/cases.jsonl` | Forty original and 160 synthetic cases; no expected labels |
| `fixtures/labels.jsonl` | Independently authored verdicts, citations and rationales, all **draft** |
| `fixtures/splits.jsonl` | Fixed grouped 50 tuning / 150 test split |
| `fixtures/employees_overlay.jsonl` | Explicit synthetic employee/intern/contractor roles |
| `fixtures/manifest.json` | Every added scenario/field, roles, classification mappings and hashes |
| `policy.json` | Versioned company and tax packs with review status and assumptions |
| `evaluation/predictions.jsonl` | Every method/case/run prediction or failure |
| `evaluation/summary.json` | Versioned metrics, hashes, configurations and coverage |
| `audit.json` | Demo-ledger verdicts, provenance, questions, fixes and evidence coverage |

Smaller commands:

```powershell
purchase-backend ingest --company company-072 --output artifacts/demo
purchase-backend ingest --company all --output artifacts/all
purchase-backend fixtures --records artifacts/all/purchases.jsonl
purchase-backend check --cases artifacts/backend/fixtures/cases.jsonl
```

## Data semantics

YAML uses `CSafeLoader`/`SafeLoader`. The archive is streamed, retaining one company's parsed source entities at a time. Unsafe member paths, duplicate IDs/files, missing joins, mismatched vendor/date/amount, invalid cents, line arithmetic, and overpayments raise errors. The participant archive must group entity files by company; an interleaved custom archive is rejected explicitly.

`case_id`, vendor, employee, payment, bank, and item references are company-scoped. Accounting lines preserve the **original account ID**, interpreted together with `company_id`; original item IDs are also retained. No source account is overwritten with a demo tax classification.

`amount_cents` is the original bill's purchase amount. `settlements[].allocated_cents` records each payment allocation, with its own date and bank references. Sum allocations for cash paid; count cases for purchases. A bill, payment, and bank movement never become three purchases. Unpaid bills and non-bill bank outflows (including payroll/financing) are excluded from this purchase-audit view and counted separately in its manifest. This is not a replacement for the entire general ledger.

Missing purchase time, employee link, role, receipt, approval, event purpose and tax qualification remain unknown. Source employee job titles do not establish policy roles. Account names alone do not establish expense kind. Each case includes source-document references and field provenance. Synthetic records and evidence are separate additions.

The original split uses 10 purchases from `company-072` for tuning and 30 from `company-001` for test. Different companies prevent source-company overlap. Synthetic cases are 32 independently specified scenarios with five wording variants each; every variant of a scenario stays in one split. Forty synthetic tuning cases and 120 synthetic test cases complete the 50/150 split. The scenario families share the same draft demo policy intentionally.

Expected labels are handwritten in the fixture definitions, not obtained by calling the engine. They require human review against the policy text before making model-quality claims. Update `review_status` to `reviewed` only with `reviewed_by` and a rationale. The five variants are simple controlled examples, not 160 independent real-world observations. A high keyword score on these templates does not establish Jev/Gemini performance or superiority.

## Policy semantics

`PolicyEvaluator` compiles JSON boolean expressions to Z3. Supported operators: `fact`, `and`, `or`, `not`, `eq`, `ne`, `gt`, `ge`, `lt`, `le`. Facts use strict booleans, integer cents/days, bounded enums and explicit unknowns; see `FACT_TYPES` in `models.py`. A rule has `id`, `layer`, `when`, `require`, and optional explanatory `fix`. Custom packs can be supplied with `--policy PATH` to check, audit and evaluate. Treat evaluator instances as immutable; create a new instance after changing policy.

The default `demo-2026-10-17-v1` is explicitly **draft**. It implements only the user-approved PDF examples:

| Rule | Company requirement |
| --- | --- |
| `COMP-3.4` | Strictly more than 3,500 cents requires pre-approval; exactly $35 does not trigger it |
| `COMP-5.2` | Intern rideshare/airfare purchases require an actual company-event purpose |
| `COMP-RECEIPT-60` | If receipts are required, evidence of submission by day 60 is required after day 60 |

These stable IDs belong to this demo pack. No unspecified policies from the PDF's “about 15” are invented. Whether a receipt is required is itself a fact; absent company evidence, it stays unknown.

The separate tax reference pack documents [IRS Publication 463 (2025)](https://www.irs.gov/publications/p463), checked October 17, 2026. It covers ordinary qualifying business meals (50%-limited classification), qualifying employee recreation meals (outside that limitation), and ordinary entertainment without an exception (nondeductible classification). Qualification includes business purpose, employee presence, lavishness, entertainment separation and applicable exceptions. A company event alone does not establish the employee-recreation exception. The typed `qualified_employee_recreation` fact means the exception's conditions have been established, including primarily benefiting employees other than highly compensated employees.

Missing tax qualification facts require review even if the account code appears correct. Known exceptions outside this narrow pack return `not_applicable`: that means outside the encoded checks, not deductible, tax-exempt, or authorized to spend. Separately stated meals must satisfy the normal-price condition documented in the synthetic evidence. Unsupported tax situations need specialist review. The company's strict 60-day rule is **not** a universal IRS deadline; the accountable-plan 60-day provision is a safe harbor.

Each evaluation returns separate `company` and `tax` layers:

- `violation`: no completion of unknown facts can satisfy the layer; only definitively violated individual rules are cited.
- `undetermined`: facts allow different outcomes, or tax qualification remains uncertain.
- `compliant`: all possible completions satisfy the applicable requirements (tax qualification must also be established).
- `not_applicable`: no encoded rule can apply.

`status` separately reports `ok`, `unsupported`, `conflicting_policy`, or `error`. No transaction verdict is manufactured for an invalid policy. Conflict checking includes multi-rule overlaps, with a limit of 10 rules per layer to bound exhaustive checks. Unsupported operators, facts and larger packs are reported explicitly. Solver timeouts become errors.

Questions identify unknown facts and the outcomes of candidate answers. `deciding_alone: false` means the fact is needed together with other missing evidence. Fixes are proposed actions requiring re-evaluation; they never mutate a fact or grant approval. Approval requests are not evidence. For posted purchases, later approval cannot cure missing historical pre-approval. A same-date approval without purchase time remains uncertain. Existing pre-purchase approval is not erased by a later confirmation. Receipt records use their actual submission date; uploading a late receipt cannot erase a missed deadline.

## Person A handoff

```python
from jev_z3.backend import Approval, BackendService, Fact, load_records

service = BackendService()
cases = load_records("artifacts/backend/fixtures/cases.jsonl")
case = next(c for c in cases if c.case_id.endswith(":28:0"))
result = service.check(case)                  # EvaluationResult
case, result = service.answer(case, {
    "business_purpose": Fact(value=True, source="confirmed_answer", evidence_id="answer-1")
})
case, result = service.approve(case, Approval(
    evidence_id="approval-1", approver_id="manager-1", approved=True,
    approved_at="2026-10-06T12:00:00Z"
))
rows = service.ledger(cases)                   # records + matching cached audit results
audit = service.audit(cases)                   # audit results and evidence coverage
```

| Route owned by Person A | Shared service |
| --- | --- |
| `POST /check` | Construct a validated `PurchaseCase` from extraction and trusted metadata; `service.check(case)` |
| `POST /cases/{id}/answer` | `service.answer(case, confirmed_facts)`; returns updated case and result |
| `POST /cases/{id}/approve` | Authenticate approver, create timestamped `Approval`, call `service.approve` |
| Receipt evidence | `service.attach_receipt(case, Receipt(...))` |
| `GET /ledger` | `load_records` and `service.ledger`; filter/paginate at route boundary |
| `POST /ledger/audit` | `service.audit(company_cases)` |
| `GET /eval` | Read the latest configured `evaluation/summary.json`; preserve its hashes and coverage |

Authentication, approved-answer permissions, durable case storage, database transactions and authorization remain Person A's responsibilities. The service cache is process-local and keyed by company, case ID, policy version, policy hash and complete case-content hash; results also carry a resolved-facts hash. Changing evidence or policy invalidates reuse. Persist those identifiers together when caching in a database. Z3 calls should be serialized or isolated per worker process; do not share this evaluator concurrently across threads.

**Current API contract differs.** Person A's added `api/models.py` has one three-state verdict, mandatory employee IDs, USD floats, and non-null benchmark numbers. These versioned backend results intentionally preserve four-state, separate-layer verdicts, missing employee IDs, integer cents, unavailable metric values and diagnostics. The new services are not yet wired into those routes. Person A should add a versioned response or an explicit adapter preserving these fields; do not coerce unknown employee/approval evidence, `not_applicable`, or unavailable model metrics into fabricated values. Existing `engine` policies and their scores are a different policy version, not interchangeable with this pack. No API model or route is overwritten by this work.

## Evaluation adapters

Default execution runs the independent Python keyword baseline, with no Z3 verdict computation or network calls. It reads the same sanitized inputs as the models and uses three-valued rules. A benchmark always requests three independent runs per selected method.

```powershell
# Missing model predictions are explicitly unavailable, not keyword substitutes.
purchase-backend evaluate --methods keyword gemini_judge gemini_facts_z3 jev_facts_z3

# Import the teammate's actual extraction runs, offline.
purchase-backend evaluate --methods jev_facts_z3 --predictions artifacts/jev_predictions.jsonl
```

Prediction JSONL contract (one row **per case per run**, with runs 1, 2 and 3):

```json
{"case_id":"company-072:synthetic:04:0","method":"jev_facts_z3","run":1,"model":"actual-model-version","inference_backend":"actual-provider","status":"ok","facts":{"expense_kind":{"value":"rideshare","source":"jev","probability":0.99},"at_company_event":{"value":true,"source":"jev","probability":0.97}},"latency_ms":12.5,"cost_usd":null}
```

Allowed extracted facts are `expense_kind`, `client_present`, `at_company_event`, `business_purpose`, `employee_present`, `lavish`, `qualified_employee_recreation`, `other_tax_exception`, `separately_stated_meal`, and `mixed_entertainment`. Models cannot replace amount, role, approval, receipt, or coded-account metadata. Omitted facts remain unknown. `probability` here is **confidence in the supplied value**, not probability that a boolean is true. Convert Jev's P(true) to P(the returned value) for false answers, or supply an already-gated value with `probability: null`. Values with confidence below the configured threshold (default .85) become unknown. Record missing time/cost as null, never zero.

For `gemini_judge`, supply `judgment` instead of `facts`:

```json
{"case_id":"company-072:synthetic:04:0","method":"gemini_judge","run":1,"model":"actual-model-version","inference_backend":"gemini_api","judgment":{"company_verdict":"compliant","company_rule_ids":[],"tax_verdict":"not_applicable","tax_rule_ids":[]},"latency_ms":123.4,"cost_usd":null}
```

Failures can supply `status: "error"` and `error` instead of a payload. Invalid facts, citation IDs, duplicate predictions, and mismatched identities are reported/rejected explicitly. One recorded run is never copied three times to claim repeatability.

Teammate Python adapters can implement `adapter(model_input, policy_pack, run) -> Prediction` and be passed as `adapters={"jev_facts_z3": adapter}` to `run_benchmark(..., allow_live=True, methods=("jev_facts_z3",))`. Pass nonsecret adapter configuration with `adapter_configuration`. A callable requires explicit live permission because it may perform network requests. `model_input(case)` strips all target semantic facts and excludes expected verdicts, rationales, group/scenario names and split assignments. The runner never passes labels to adapters. Extractor outputs are merged into a new case; no gold semantic facts are retained.

The Gemini judge adapter uses the official [generateContent API](https://ai.google.dev/api/generate-content) with structured JSON output. A live run requires explicit method selection, `--allow-live`, `GEMINI_API_KEY`, and `GEMINI_MODEL` (or `--gemini-model`). It performs 600 calls for 200 cases; there is no automatic retry or fallback. Supply current token pricing explicitly to estimate costs:

```powershell
# Set credentials/model in the process environment first; never commit them.
purchase-backend evaluate --methods gemini_judge --allow-live
# Optional: --input-per-million PRICE --output-per-million PRICE
```

No live model results are included in the checked run. The latest main branch includes `api/jev_live.py`; it still needs an adapter to this benchmark's prediction contract (including conversion of boolean P(true) to confidence in the supplied value). Gemini extraction and ASI:One integration remain separate teammate work.

## Metrics and review

Exports include combined/company/tax accuracy, citation micro precision/recall/F1, exact three-run agreement, median/p95 latency, API cost per 1,000, uncertainty rates, successful and decidable coverage, and error counts. Each method is reported overall and by original/synthetic × tuning/test. Accuracy uses successful predictions only; inspect coverage alongside it. Repeatability requires three successful independently supplied runs. Missing prices/timing remain null; reported samples/coverage show partial cost or latency observations. Failed-call charges and local compute costs are not estimated. p95 uses nearest rank. Empty citation denominators use precision/recall 1. A record's `execution_mode` distinguishes measured local, recorded and live results.

Data, labels, splits, policy and imported-prediction hashes accompany model identities, evaluator version and configuration. Preserve tuning/test separation when choosing thresholds; this runner does not fit thresholds on test labels. Keep generated labels marked draft until reviewed.

Tests cover ingestion joins and installments, company scoping, exact cents and duplicate prevention, safe YAML, missing facts, $35 and days 60/61, intern exceptions, approval timing, classification conflicts including three-way conflicts, multiple violations, workflow re-evaluation, cache invalidation, split leakage, target-fact isolation, invalid/missing predictions, adapter failures, metrics, and a mocked Gemini API. The all-company build supplies the archive integration validation; ordinary unit tests need no external data or API key.
