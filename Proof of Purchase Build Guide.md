# Proof of Purchase: Build Guide

Oct 17, 2026 · @Advay

## What we're building today

GOAL: the demo shows one purchase end to end: a new hire asks "can I buy this?", gets a proven answer, a manager approves it on the dashboard, a simulated card authorization is issued for exactly that amount, and the purchase lands in a QuickBooks ledger that the same rules audit in full. Z3 makes every decision; the models only read messy text into facts.

**In scope**

- **Rule engine (Z3):** verdicts with cited rules, the smallest fix for a "no", the one question worth asking, and audits of the policy itself.
- **Rule packs:** a demo company policy plus IRS rules for meals, entertainment and the 60-day receipt deadline.
- **Bank-rule checker:** finds QuickBooks bank rules that overlap or can never fire.
- **Ledger audit:** every transaction in Intuit's synthetic data, checked against the rules.
- **Purchase check:** a form where a new hire pastes an item, price and reason, and gets a verdict. This is the minimal stand-in for the shopper.
- **Surfaces:** a web dashboard (with an Approve button for managers) and an ASI:One agent.
- **Evaluation:** our approach against keyword rules and an LLM judge, on the same labeled transactions.

**Cut for now** (designed so each can be added later without touching the engine)

- Browsing and comparing products automatically; see the last section.
- Real Visa authorization. We return a mock authorization with the limits a real card control would get.
- Manager approval by text; approvals use a dashboard button instead. Receipt photos through Step 5, the LLM formalizer, and the Payment Protocol are also cut unless the core is done early.

**One demo run**

1. A new hire types: "Client dinner Thursday with Acme's CFO, about $48."
2. Jev reads it into facts; Z3 says it needs pre-approval and must be coded as a 50% meal.
3. A manager clicks Approve on the dashboard. The verdict flips to compliant, and a mock card authorization for $48 appears.
4. The ledger view shows the purchase posted with the right account, then the full audit of Intuit's data: violations, conflicting bank rules, and the evaluation numbers.

## How it works

A purchase request becomes typed facts, Z3 decides against the rules, and only two outcomes ever involve a person: a fact nobody knows yet, or a violation whose fix is a manager's approval. Every answer re-runs the proof, so the verdict on screen is always the solver's.

&#91;embedded content: one purchase, end to end\]

1. **Read.** The request text goes to Jev with one question per fact. Confident answers (probability at least 0.85 or at most 0.15) become facts; the rest stay unknown. Amount, time and the employee's role come from the form and records, never from a model.
2. **Decide.** Z3 returns compliant, violation or undetermined, with the rules and facts behind it.
3. **Resolve.** For a violation, the smallest fix is shown; if it's "get pre-approval", the case waits on the dashboard's approvals tab until a manager approves it. For undetermined, the one deciding question is asked. Either answer goes back through step 2.
4. **Pay and post.** A compliant case gets a mock card authorization for exactly that amount, tagged with a hash of the proof, and is posted to the ledger with the account the rules require.
5. **Audit.** The ledger view runs the same rules over every transaction in Intuit's data, so the purchase and the whole history are judged the same way.

## Architecture and repo layout

One FastAPI server holds all the logic; the dashboard and the ASI:One agent are thin clients of it, so they can never disagree. Each person owns one color below and touches the others only through the API contract.

&#91;embedded content: architecture · colored by owner\]

Gemini is used only as the comparison baseline in the evaluation, never in a verdict. One monorepo:

```
proof-of-purchase/
  engine/          A  rules.py, bank_rules.py, demo_policy.json, irs_pack.json, test_rules.py
  api/             A  main.py (FastAPI), db.py (SQLite), cases.py, ledger.py, explain.py
  data/            B  load_intuit.py, SCHEMA.md, employees.csv, approvals.csv, eval_labels.csv
  extract/         B  jev.py (Jev calls), mapping.py (QuickBooks category -> coded_account)
  eval/            B  run.py, baselines.py, results.json
  agent/           B  agent.py (uAgents), cards.py, README.md (for ASI:One discovery)
  web/             C  Next.js app: app/check, app/ledger, app/rules, app/approvals, app/eval
  .env.example
  README.md           what it does, how to run, every change to Intuit's data
```

## Tech stack

Python everywhere the reasoning happens; TypeScript only for the dashboard. One GitHub monorepo, one FastAPI server that everything else calls.

| Tool | Its one job | Owner |
| --- | --- | --- |
| Python 3.11 + `z3-solver` | Every verdict, citation, fix, question and audit | A |
| FastAPI + Pydantic + uvicorn | The API in the contract below; the only thing the surfaces talk to | A |
| SQLite (Postgres later) | Policies, transactions, facts, verdicts, approvals | A |
| pytest | Engine tests; run on every push | A |
| pandas | Load and clean Intuit's ledger tarball | B |
| Jev via `typesafe-sdk` | Read messy text into facts with probabilities | B |
| Gemini API | Labels for the LLM-judge baseline in the evaluation; later, drafting rules from policy text | B |
| `uagents` ≥0.25.5 | The ASI:One agent: Chat Protocol and cards | B |
| Next.js + Tailwind | Dashboard: purchase check, ledger audit, rules, evaluation | C |
| Photon `spectrum-ts` (Node) | Cut for now; add back for approval by text | C |
| Sentry (Python + Next.js) | Traces across the pipeline, Logs, Session Replay | C |
| Vultr VM + Vercel | API and agent on Vultr; dashboard on Vercel | C |

**Environment variables** (one shared `.env`, never committed): `TYPESAFE_API_KEY`, `GEMINI_API_KEY`, `AGENT_SEED`, `SENTRY_DSN`, `API_URL`.

## The Z3 engine in detail

The engine turns JSON rules into Z3 formulas once, then answers four questions per transaction in milliseconds. Starter code is in `engine/rules.py` and `engine/bank_rules.py`, with nine tests in `engine/test_rules.py`. It was written without running Z3 (the sandbox it was written in could not install it), so Person A's first job is `pip install z3-solver pytest && pytest -q engine/` and fixing anything that fails.

**1. Facts.** A fixed list of typed variables, one per thing a rule can mention. Enums are stored as Z3 integers (an index into the value list), so everything stays in fast linear arithmetic.

| Fact | Type | Where it comes from |
| --- | --- | --- |
| `role` | enum: employee, contractor, intern | employee record |
| `expense_kind` | enum: meal, rideshare, airfare, hotel, software, equipment, entertainment, other | Jev Choice |
| `coded_account` | enum: meals\_50, meals\_100, entertainment\_0, travel, office, other | QuickBooks category, mapped |
| `amount` | real, USD | ledger or form |
| `hour` | int, 0–23 | timestamp |
| `days_since_purchase` | int | timestamp |
| `receipt_attached`, `pre_approved` | bool | ledger, approvals table |
| `client_present`, `at_company_event` | bool | Jev probability, else ask |

**2. Rules.** Each rule is "when this is true, that must be true", written as JSON that a person can review and an LLM can later draft. Each keeps its source sentence and a layer (company or IRS).

```json
{"id": "5.2", "layer": "company",
 "text": "Interns get no transport reimbursement except at company events.",
 "when": {"and": [{"eq": ["role", "intern"]}, {"in": ["expense_kind", ["rideshare", "airfare"]]}]},
 "require": "at_company_event"}
```

Operators: `and`, `or`, `not`, `eq`, `neq`, `gt`, `ge`, `lt`, `le`, `in`. The compiler turns each rule into `Implies(when, require)`; the policy is compliant when every rule holds.

**3. Verdict: `check(facts)`.** Known facts become equalities; unknown facts stay free variables, so the solver considers every possible value.

1. For each rule, ask Z3 whether the rule can hold given the facts. If not, the rule is **violated**, and the unsat core names the facts that break it ("amount and pre\_approved"). Checking rule by rule means every broken rule is cited, not just the first one Z3 finds.
2. If no rule is broken, ask whether the transaction could still fail for some value of the unknown facts. If not, it is **proven compliant**, and the rules whose conditions applied are listed.
3. Otherwise the verdict is **undetermined**: it depends on a fact we don't know yet.

```python
def _fact_core(self, facts, goal):
    s = z3.Solver(); s.set(unsat_core=True)
    s.add(*self.dom, goal)
    for n, c in self.facts_eq(facts).items():
        s.assert_and_track(c, z3.Bool(f"fact_{n}"))   # label each fact
    if s.check() == z3.sat: return None
    return [the fact names in s.unsat_core()]
```

**4. The fix: `fix(facts)`.** `z3.Optimize` keeps everything a person can't change as hard constraints (who they are, what they bought, when) and adds a soft constraint "keep the current value" for each thing they can change, weighted by effort: recode the account or attach a receipt (1), get pre-approval (2), spend less (3). The cheapest set of broken soft constraints is the fix. If amount changes, a second pass maximizes it, so the answer reads "keep it at or under $35" rather than an arbitrary number. If even that can't work, the answer is "no change you control makes this compliant."

**5. The one question: `questions(facts, p_yes)`.** For each unknown yes/no fact, run `check` with it set to yes and to no. If the two verdicts differ, it is worth asking; sort by how unsure Jev was (closest to 0.5 first). `facts_from_probs` fixes a fact only when Jev's probability is at least 0.85 or at most 0.15; everything between stays unknown. Tune both thresholds on the evaluation set.

**6. Audits of the rules themselves.**

- `audit()`: a **dead rule** has a condition no transaction can meet; a **conflict** is two rules that can both apply but can't both be satisfied. Each conflict comes with an example transaction.
- `disagreement(a, b)`: two readings of one sentence ("over $35" as more than vs at least) and the exact case where they differ, which here is $35 without pre-approval.

**7. Bank rules: `check_bank_rules(rules)`.** QuickBooks bank rules are already precise: description contains some words, amount in a range, assign a category, first match wins. Z3's string theory handles `Contains`. Two checks per pair: a later rule is **shadowed** if every transaction it matches is taken by an earlier one, and two rules **overlap** if one transaction matches both with different categories, with that transaction shown. Expect some noisy overlaps ("UBERAMAZON"); filter to overlaps where one rule's words include the other's before showing them.

**Speed.** Each check is a handful of small solver calls. Reuse one `Policy` object per policy version; if the ledger audit gets slow, switch to one solver with `push()`/`pop()` per transaction.

## API contract

Agree on this in the first 30 minutes, then everyone builds against it in parallel. Person A ships every endpoint returning hard-coded sample JSON by 15:00, so B and C never wait on the real engine.

| Method and path | Body | Returns | Used by |
| --- | --- | --- | --- |
| `POST /check` | `{text, employee_id, amount?, timestamp?}` | A **case** (below) | Dashboard, agent |
| `POST /cases/{id}/answer` | `{fact, value}` | The updated case | Agent, dashboard |
| `POST /cases/{id}/approve` | `{approver, approved}` | The updated case; sets `pre_approved` | Dashboard approvals tab |
| `POST /cases/{id}/authorize` | none | Mock card authorization, only if compliant | Dashboard |
| `GET /ledger` | `?company=&verdict=` | Transactions with their verdicts | Dashboard |
| `POST /ledger/audit` | `{company}` | Counts by verdict and rule, top violations | Dashboard, agent |
| `GET /policy` · `POST /policy/audit` | none | Rules · dead rules and conflicts | Dashboard |
| `POST /bank-rules/check` | `{rules: [...]}` | Shadowed and overlapping rules | Dashboard |
| `GET /eval` | none | The evaluation table | Dashboard |

**A case** is the one shape every surface renders:

```json
{
  "case_id": "c_8f2a",
  "verdict": "violation",
  "facts": {
    "expense_kind": {"value": "meal", "source": "jev", "p": 0.97},
    "client_present": {"value": true, "source": "jev", "p": 0.91},
    "amount": {"value": 48, "source": "user"},
    "pre_approved": {"value": false, "source": "approvals"}
  },
  "violations": [
    {"rule": "3.4", "text": "Any expense over $35 needs manager pre-approval.", "because": ["amount", "pre_approved"]},
    {"rule": "IRS-meal", "text": "Business meals outside company-wide events are 50% deductible.", "because": ["expense_kind", "at_company_event", "coded_account"]}
  ],
  "fix": [{"fact": "pre_approved", "from": false, "to": true},
          {"fact": "coded_account", "from": "travel", "to": "meals_50"}],
  "questions": [],
  "explanation": "Needs manager approval because it's over $35 (rule 3.4). Code it as a 50% meal (IRS)."
}
```

**Mock authorization** returned by `/authorize`: `{auth_id, amount_limit, merchant_category, expires_at, proof_hash}`. The `proof_hash` is a SHA-256 of the case's facts, rule versions and verdict, so the card limit can be traced back to the exact proof. When the Visa sandbox is available, this endpoint is the only thing that changes.

**Explanations** are filled from a template using each rule's `text` and the `because` facts, never written freely by an LLM, so the words can't contradict the proof.

## Who does what

Three lanes that meet only at the API contract: **A** owns the engine and API, **B** owns data, models, the ASI:One agent and the evaluation, **C** owns everything a judge sees. Tick tasks off here as you go.

### Person A: engine and API (Python)

*By 15:00*

- [ ] Create the repo in the layout above and push the starter `engine/` folder
- [ ] `pip install z3-solver pytest`, run `pytest -q engine/`, fix anything that fails
- [ ] FastAPI app with every endpoint in the contract returning sample JSON

*By 20:00*

- [ ] `/check` for real: B's extractor → `facts_from_probs` → `check`, `fix`, `questions` → case JSON with template explanation
- [ ] SQLite tables: `cases`, `transactions`, `verdicts`, `approvals`, `policy_versions`
- [ ] `/answer`, `/approve` and `/authorize` (mock authorization with `proof_hash`)
- [ ] With B, map QuickBooks categories to `coded_account`

*By 02:00*

- [ ] `/ledger/audit` over every transaction, cached per policy version
- [ ] `/policy/audit` and `/bank-rules/check`, with the noisy-overlap filter
- [ ] Full demo policy (about 15 company rules) plus the IRS pack, with a test per rule
- [ ] Keyword-rules baseline for the evaluation
- [ ] Stretch: what-if, which re-runs the ledger with one edited rule and returns the verdicts that flip

### Person B: data, Jev, agent, evaluation (Python)

*By 15:00*

- [ ] Download and unpack Intuit's tarball on a laptop; write what's in it to `data/SCHEMA.md`
- [ ] Get a Jev key (Intuit's table, or the Vercel AI Gateway route) and make one test call
- [ ] Deploy a hello-world ASI:One agent with a mailbox and chat with it

*By 20:00*

- [ ] Loader: ledger → `transactions` with amount, timestamp, memo, vendor, category, employee
- [ ] Extractor: one Jev call per transaction (`Choice` for `expense_kind`; `Noul` for `client_present` and `at_company_event`), returning probabilities
- [ ] Synthetic employees and approvals tables; list every data change in the README

*By 02:00*

- [ ] Labeled evaluation set of about 200 transactions, including injected violations and edge cases
- [ ] LLM-judge baseline (Gemini given the policy text and the transaction)
- [ ] `eval/run.py`: accuracy, same-answer-on-rerun, median latency, cost per 1,000 transactions
- [ ] Agent: calls `/check`; `form` card to confirm facts, `detail` card for the verdict; `case_id` in every card payload
- [ ] Agent README with summary, examples, limitations and the two hackathon badges

*By 10:30*

- [ ] Final evaluation run; results served by `/eval`
- [ ] At least 10 real conversations with the agent before judging

### Person C: dashboard, approvals, deploy (TypeScript)

*By 15:00*

- [ ] Next.js app with four pages (Check, Ledger, Rules, Evaluation) rendering the contract's sample JSON
- [ ] Vultr VM running the API stub; dashboard on Vercel
- [ ] Approvals tab stub listing pending cases

*By 20:00*

- [ ] Check page: form → case card with verdict chip, facts and probabilities, cited rules, fix, question buttons
- [ ] Approvals tab: each pending case with its cited rule and an Approve button that calls `/approve`; the page updates live
- [ ] Authorization card: limit, merchant category, proof hash

*By 02:00*

- [ ] Ledger page: verdict chips, filters, detail drawer, audit summary at the top
- [ ] Rules page: each rule beside its sentence, policy audit issues, bank-rule checker with example transactions
- [ ] Evaluation page from `/eval`
- [ ] Sentry: tracing, Session Replay and Logs on web and API

*By 10:30*

- [ ] Visual polish, then record the 3–5 minute demo video

### Everyone, 10:30–12:00

- [ ] Devpost entry, public repo, README with agent name and address
- [ ] Register through the LA Hacks ASI:One submission agent
- [ ] Rehearse the 4-minute demo twice

## Timeline

Five gates, each checked together in a 10-minute standup; if a gate slips, cut from the list below before starting anything new.

&#91;embedded content: timeline · phases not to scale\]

**Cut order if behind** (first cut first): the shopper, the what-if stretch, Sentry beyond tracing, the bank-rule checker page (keep its API), the approvals tab (set `pre_approved` by hand in the demo). Never cut: `/check` with cited rules and fix, the ledger audit, the ASI:One agent, the evaluation table.

## Evaluation plan

Intuit's brief asks for evidence on realistic data that beats classical ML and LLM approaches, so the evaluation is a deliverable, not an afterthought. The claim to test: Jev plus Z3 gives correct, repeatable verdicts at a latency and cost that make checking every transaction practical.

**Data.** About 200 transactions from Intuit's ledgers, plus injected cases that exercise each rule: a client dinner over $35, an intern's ride, a meal coded to travel, a receipt missing after 75 days. A person labels each one with the expected verdict and the rules it breaks, by reading the policy, never by running our engine. Hold out 150; use the other 50 to tune the 0.85 and 0.15 thresholds. List every injected or edited row in the README.

**Four systems on the same rows.**

1. **Keyword rules:** regexes on the memo plus the amount thresholds (Person A).
2. **LLM judge:** Gemini gets the policy text and the transaction and returns a verdict and rule IDs as JSON.
3. **LLM facts + Z3:** Gemini extracts the facts, Z3 decides. This isolates what Jev adds over an LLM doing the same extraction.
4. **Jev + Z3:** ours.

**Measures.**

| Measure | How |
| --- | --- |
| Verdict accuracy | Against the human labels, held-out rows only |
| Rule citation F1 | Rules cited versus rules labeled |
| Same answer on rerun | Run each system 3 times; share of rows with identical verdicts |
| Median latency per transaction | Wall clock, extraction plus decision |
| Cost per 1,000 transactions | From token usage and each provider's published price |
| Questions per transaction | How often ours asks, and how often one answer settles the verdict |

Show one table and one chart of accuracy against latency. Report where ours loses too; judges trust an evaluation that admits a weakness.

## Adding the shopper later

The shopper is the same `/check` run once per product instead of once per purchase, so it needs a product source and a results page, not engine changes. Start it only after the 02:00 gate is met.

1. **Products:** a JSON file of 30–50 fake hotel and equipment listings (name, price, merchant, short description). No scraping.
2. **Facts per listing:** one Jev call per listing, all in parallel, plus the new hire's own facts (role, trip dates). Add any new facts the listings need, such as `nightly_rate` or `preferred_vendor`, to `SCHEMA`.
3. **Filter and rank:** run `check` per listing. Show compliant ones first, greyed-out ones with their one-line reason, and "needs approval" ones with an Approve button that uses the same approvals tab.
4. **Buy:** the chosen listing becomes a case and goes through `/authorize`, exactly like the purchase form.

This is also where Jev's speed shows most: dozens of listings checked while the page loads, which is the live-filtering story for the Intuit and Visa judges.
