# Jev-Z3: Natural Language Accounting Rule Classifier to Z3 Logical Proofs

A formal verification pipeline that translates natural language expense policies, procurement controls, and QuickBooks accounting rules into typed logical parameters, then proves transaction compliance, policy consistency, and ledger balancing using the **Z3 SMT Solver**.

Person B's versioned data loader, policy scenarios, and offline benchmark services are documented in [docs/backend.md](docs/backend.md). Start with `purchase-backend build` and `purchase-backend evaluate` after `pip install -e '.[dev]'`.

---

## 💡 The Core Problem

Traditional generative AI models (like GPT-4 or Claude) hallucinate when tasked with enforcing financial compliance rules and complex accounting logic. In high-stakes financial operations:
- A single undetected policy breach can cause regulatory fines or unauthorized spend.
- Conflicting corporate policies create ambiguous loopholes.
- Splitting purchases across multiple transactions circumvents single-transaction limits.

**Jev-Z3** solves this by pairing two complementary paradigms:
1. **Jev (TypeSafe AI's System One Model):** A zero-shot, ultra-fast classification engine that evaluates natural language state against strictly typed questions (`choice`, `noul`, `score`) to extract calibrated parameters without generating free-form text.
2. **Z3 SMT Solver (Microsoft Research):** A formal theorem prover that mathematically verifies first-order logic assertions over transactions, detecting counterexamples, proving compliance certificates, and identifying policy contradictions.

```
                          ┌───────────────────────────┐
                          │   Natural Language Rule   │
                          │   or QuickBooks Policy    │
                          └─────────────┬─────────────┘
                                        │
                                        ▼
             ┌─────────────────────────────────────────────────────┐
             │       Jev 'System One' Decision Engine              │
             │   - Choice: Domain, Scope, Category, Operator       │
             │   - Noul: Receipt, VP Approval, PO, W-9, Audit      │
             │   - Numeric Threshold Extraction & Normalization    │
             └──────────────────────────┬──────────────────────────┘
                                        │
                                        ▼
             ┌─────────────────────────────────────────────────────┐
             │          Typed Z3RuleParameters Model               │
             │  Antecedent A(T)  ==>  Obligation Consequent C(T)   │
             └──────────────────────────┬──────────────────────────┘
                                        │
                        ┌───────────────┴───────────────┐
                        ▼                               ▼
       ┌─────────────────────────────────┐   ┌────────────────────────────────┐
       │   Z3 Transaction Prover         │   │   QuickBooks & Anti-Split      │
       │   - Proof of Compliance (UNSAT) │   │   - Double-entry theorem       │
       │   - Counterexample (SAT)        │   │   - Evasion detection          │
       │   - Policy Conflict Detection   │   │   - Class tracking check       │
       └─────────────────────────────────┘   └────────────────────────────────┘
```

---

## 🚀 Features

- **Jev System One Classification:** Typed multi-question battery (`choice`, `noul`) extracting spend category, aggregation scope, approval roles, and mathematical operators.
- **Dual Inference Engine:** Seamlessly connects to TypeSafe's live cloud API when `TYPESAFE_API_KEY` is present, with an integrated local calibrated engine for offline and testing use.
- **Z3 First-Order Compliance Proofs:** Translates policy parameters into SMT logic:
  $$\forall T, \quad A(T) \implies C(T) \iff \neg(A(T) \land \neg C(T)) \text{ is UNSAT}$$
- **Counterexample Generation:** Pinpoints the exact predicate that failed when an expense violates policy (e.g. `amount = 650.0 > 500.0, approved_by_vp = False`).
- **Policy Inconsistency Detection:** Formally proves whether two corporate policies are mutually contradictory or satisfiable in their trigger intersection.
- **Anti-Split Structuring Proof:** Uses Z3 subset-sum constraint solving to catch employees who split single large purchases into multiple smaller expenses to evade approval limits.
- **QuickBooks Double-Entry Ledger Verification:** Proves the fundamental accounting theorem $\sum \text{Debits} = \sum \text{Credits}$ and verifies mandatory GL class tracking.

---

## 🛠️ Installation

```bash
# Clone the repository
git clone https://github.com/your-username/lahacks.git
cd lahacks

# Create virtual environment and activate
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install z3-solver pydantic httpx pytest
```

---

## ⚡ Quickstart CLI

Run the full interactive demonstration:
```bash
./bin/jev-z3 demo
```

### 1. Add a Natural Language Policy (with Automatic Z3 Contradiction Check)
```bash
./bin/jev-z3 add-rule 'All flights and airfare over $400 require manager approval.'
```
*If a rule contradicts existing company policies, Z3 mathematically rejects it:*
```bash
./bin/jev-z3 add-rule 'All flights and airfare over $400 are strictly prohibited and rejected.'
# ❌ RULE REJECTED: Contradiction detected in Z3 against active flight policy!
```

### 2. Ask Natural Language Purchase Queries ("Can I buy this?")
```bash
# Conditional Approval (Calculates requirements & auto-tags in QuickBooks)
./bin/jev-z3 query 'Can I buy a $650 Datadog monitoring subscription for Engineering?'

# Auto-Approved Purchase (Under threshold, clear to swipe card)
./bin/jev-z3 query 'Can I buy $45 of office supplies on Amazon?'

# Group Dining (Calculates per-attendee math: $320 / 4 people = $80/head)
./bin/jev-z3 query 'Can I take 3 clients to dinner for $320 at Nobu?'
```

### 3. List Active Rules and Inspect Compiled Z3 Formulas
```bash
# High-level summary of active rules
./bin/jev-z3 list-rules

# View rules along with their compiled Z3 first-order logic formulas
./bin/jev-z3 list-rules --z3

# Deep-dive into a specific rule (including standard SMT-LIB2 format)
./bin/jev-z3 show-rule POL-002 --smt2
```

### 4. Parse a Single Natural Language Rule into Z3 Parameters
```bash
./bin/jev-z3 parse 'Meals and entertainment over $75 require itemized receipt'
```
```bash
# Compliant transaction (meal with receipt)
./bin/jev-z3 prove --rule 'Meals over $75 require itemized receipt' --amount 120 --has-receipt

# Violation detected (meal without receipt)
./bin/jev-z3 prove --rule 'Meals over $75 require itemized receipt' --amount 120
```

### 3. Check for Policy Contradictions
```bash
./bin/jev-z3 check-conflict \
  --rule1 'All hardware purchases over $1000 are strictly prohibited and rejected.' \
  --rule2 'All hardware purchases over $1000 require purchase order and manager approval.'
```
*Output:*
```
Status:      INCONSISTENT_POLICY
Consistent:  False
Proof Type:  SMT Contradiction Proof (Unsatisfiable Intersection)
Explanation: Contradiction detected: Rules define mutually incompatible requirements on overlapping transactions.
```

---

## 🐍 Python SDK Usage

```python
from jev_z3 import JevRuleClassifier, Z3SpendProofEngine, Transaction, SpendCategory

# 1. Initialize classifier and Z3 engine
classifier = JevRuleClassifier()
prover = Z3SpendProofEngine()

# 2. Classify natural language policy into Z3 parameters
rule_text = "Software subscriptions over $500/month must be billed to Engineering and approved by a VP."
params = classifier.classify_rule(rule_text)

# 3. Formally verify an incoming transaction
tx = Transaction(
    id="tx_101",
    amount=650.0,
    category=SpendCategory.SOFTWARE_SAAS,
    department="engineering",
    approved_by_vp=True,
)

result = prover.prove_compliance(tx, params)
print(f"Status: {result.status.value}")      # PROVEN_COMPLIANT
print(f"Proof:  {result.proof_type}")        # SMT Unsatisfiability Certificate
print(f"Time:   {result.solver_time_ms} ms") # ~1.8 ms
```

---

## 🧪 Testing

Run the test suite across classifier extraction, Z3 proofs, and QuickBooks balancing:
```bash
./.venv/bin/pytest -v
```

All 15 tests verify:
- Semantic parameter extraction from diverse natural language rules
- Z3 compliance proofs and counterexample extraction
- Vacuous compliance outside threshold bounds
- Per-attendee linear arithmetic verification
- Mutual policy inconsistency detection
- QuickBooks double-entry balance and class tagging
- Anti-split evasion subset-sum detection


## Proof of Purchase API

A FastAPI server that checks a purchase request against company and IRS rules with Z3, returns the verdict with the exact rules it breaks, the cheapest fix and a proof hash, and issues a mock card authorization once the case is compliant. Every route currently answers with sample JSON and an `X-Stub: 1` header until its real implementation lands.

Run it:

```bash
python -m venv .venv && source .venv/bin/activate && pip install -e . && uvicorn api.main:app --reload --port 8000
```

Contract for every route and shape: [API_CONTRACT.md](API_CONTRACT.md). Interactive docs at `http://localhost:8000/docs`.

### Changes to Intuit's data


### Known limit

`days_since_purchase` for a ledger row with a receipt is `receipt_date - timestamp`, so a receipt filed on day 75 satisfies IRS-receipt-60. The rules catch a receipt that is *missing* after the deadline, not one that arrived late.

## Dashboard

Next.js app in `web/` (Person C). Every page fetches the API server-side on each request.

```bash
cd web && pnpm install && pnpm dev     # http://localhost:3000, needs the API on http://localhost:8000
```

One environment variable, `API_URL` (`web/.env.local` locally; `http://localhost:8000` by default). Types come from the API's own schema; regenerate after a shape change:

```bash
cd web && pnpm dlx openapi-typescript http://localhost:8000/openapi.json -o lib/openapi.d.ts
```
