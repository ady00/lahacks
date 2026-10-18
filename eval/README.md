# Evaluation

`python -m eval.run` (from the repo root, with `.env` holding `TYPESAFE_API_KEY`) rebuilds everything in this
directory. `--skip-llm` reruns only the two cheap systems and keeps the LLM rows from the previous run.
Last run: 2026-10-17 23:33 PT (LLM rows from the 23:31 full run; `--skip-llm` re-measured the other two), policy version `857f9de17290` (27 rules: `engine/demo_policy.json` + `engine/irs_pack.json`).

| system | accuracy | citation F1 | rerun agreement | median latency | cost / 1k | questions / txn |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Keyword rules | 0.832 | 0.777 | 1.000 | 0.01 ms | $0.00 | 0 |
| LLM judge | 0.991 | 0.980 | 0.933 | 3,750 ms | $10.76 | 0 |
| LLM facts + Z3 | 0.981 | 1.000 | 1.000 | 1,964 ms | $5.38 | 0.065 |
| **Jev + Z3** (this product) | **0.991** | **0.996** | **1.000** | **108 ms** | **$0.03** | 0.056 |

n = 107 held-out cases. Every prediction is in `predictions.jsonl` (system, run, case_id, verdict, rules, latency,
cost, raw model output), so each number above can be recomputed from that file.

## Held-out set (`heldout.jsonl`)

The text side comes from `api/bench_jev.py`: 45 messy purchase requests, each human-labeled for the three facts a
model has to read (`expense_kind`, `client_present`, `at_company_event`). The 4 texts with a `None` (too ambiguous
to label) label were dropped, leaving 41. Those labels were written to tune Jev's question wording, so Jev has
seen these texts before; the LLM baselines were given the identical question wording to keep that fair.

Each text is paired with 2–3 structured contexts, the facts the engine takes from records rather than from a model:
`role`, `tenure_days`, `hour`, `days_since_purchase` (always 0), `pre_approved`, `receipt_attached`
(true / false / unknown), and `amount` parsed from the text with `api.cases.parse_amount`.

- **base**: employee, 400 days tenure, noon, not pre-approved, receipt attached.
- **stress**, by expense kind: meals → intern (pre-approved) or contractor (not), at 23:00 or 05:00 for a
  breakfast; rideshare/airfare → intern, pre-approved; hotel/equipment/entertainment → 20-day new hire, not
  pre-approved; software/other → contractor, pre-approved. No receipt in every stress context.
- **approved** (every other text, plus every amount over $500): employee, pre-approved, receipt *unknown*.

Gold: 67 violation, 35 compliant, 5 undetermined. Every rule in the company pack fires in gold at least once
except 6.5 (no labeled client meal over $150), 9.1 (no rideshare over $75) and 4.1 / IRS-receipt-* (days since
purchase is 0 by construction). The IRS coding rules are never violated in gold because `coded_account` is derived.

## Gold labels

`eval/gold.py` is a 40-line three-valued (true / false / unknown) interpreter over the rule JSON with no Z3 and no
shared code with `engine/rules.py`. A rule is violated when its `when` is true and its `require` is false; unknown
when either side is unknown and the outcome is not already decided. The case is `violation` with the set of violated
ids if any rule is violated, else `undetermined` if any rule is unknown, else `compliant`. `coded_account` is set
from the human labels the way the IRS pack codes it (meal → meals_50, meal at a company event → meals_100,
entertainment → entertainment_0, rideshare/airfare/hotel → travel, software/equipment → office, other → other).

**Gold vs Z3 check.** Feeding each case's gold facts straight into `api.cases.POLICY.decide(facts, {})` gives the
same verdict and the same rule set on 107/107 cases (`notes.gold_vs_z3_agreement` in `results.json`). This checks
that the Z3 compilation of the 27 rules matches an independent reading of them; it does not make the Z3 systems'
scores trivial, because those systems get the text, not the human labels.

## The four systems

All four receive the same structured context. They differ only in how the text is read and how the rules are applied.

1. **Keyword rules** — `engine.keyword_baseline.extract_stub` + `keyword_verdict`, the repo's no-Z3 if/else
   checker, on a transaction row: memo = text, amount, timestamp = today at `hour`, `receipt_attached`, and
   `qb_category` set from the *human* expense-kind label (what a bookkeeper's QuickBooks category would say).
   That category is generous to the baseline. It still cannot see `role` or `tenure_days` (a transaction row has
   neither), cannot say undetermined, and cannot code `meals_100`.
2. **LLM judge** — the local Claude Code CLI (`claude -p … --model sonnet`, resolved to `claude-sonnet-5`) with
   all tools, settings, CLAUDE.md and MCP servers disabled, given the 27 rules (id + text), the structured context,
   the text, a note that the IRS rules only decide coding, and the three-verdict definition. It must answer one
   JSON object `{"verdict", "rules"}`; a malformed answer counts as wrong (none occurred).
3. **LLM facts + Z3** — the same CLI answers only the three typed reading questions, using the exact wording in
   `api.jev_live.QUESTIONS`, as probabilities; then `facts_from_probs` (0.85 / 0.15 thresholds) + the structured
   context → `POLICY.decide`.
4. **Jev + Z3** — `api.jev_live.extract_with_meta` (Typesafe System One, `jev-1.13.0`) → `facts_from_probs` +
   context → `POLICY.decide`.

## Metrics

- **accuracy**: verdict equals gold.
- **citation F1**: micro-averaged F1 of the predicted set of violated rule ids against gold over all cases; a
  compliant or undetermined prediction has an empty set.
- **rerun agreement**: identical verdict *and* rule set on a second run. Keyword rules and Jev + Z3 were run twice on
  all 107 cases; the two LLM systems on a fixed random 30-case subset (`random.Random(0)`) to bound cost.
- **median latency**: Keyword — wall time of extract + verdict. LLM systems — the CLI's reported `duration_ms`
  (model time, excluding ~1 s of process start-up; wall time medians were 4.5 s and 2.7 s), plus Z3 decide time for
  system 3. Jev + Z3 — Jev's HTTP round trip + Z3 decide time.
- **cost / 1k**: mean cost per case × 1000. LLM systems: the CLI's `total_cost_usd` (list price; it includes a
  small Haiku side-call the CLI makes, about $0.001 per call). Jev: input tokens × **$0.042 per million input
  tokens, output free**, the price third-party trackers (llmreference.com, eesel.ai) quote from
  docs.typesafe.ai; we could not open the official pricing page directly, so treat it as an assumption. At ~654
  input tokens per call that is $0.0000275 per case. Keyword: 0.
- **questions / txn**: mean number of yes/no questions Z3 would ask (`decision.questions`); 0 for systems that
  never ask.

LLM calls made: 274 (137 per LLM system), total $1.96.

## Where ours loses

**Jev + Z3 missed one case**, h028: "Cab from the hotel to the conference center, $25" for an intern. The human
label says it was not a company event, so rule 5.2 is violated. Jev gave `at_company_event` p = 0.18, just above
the 0.15 floor, so the fact stayed unknown and the system returned *undetermined* with one question ("was this at a
company event?") instead of the violation. That is the designed behaviour at the edge of the threshold, but it is
counted as wrong here. It is the only miss in 107 cases and it reproduced identically on rerun.

**The LLM judge ties on accuracy** (0.991; its one miss was calling a pre-approved $79 Zoom add-on undetermined,
and on rerun it flipped that case to compliant and flipped a $1,200 no-receipt registration from violation to
compliant). It loses on citations (omits 3.4 on an escape-room ticket, and omits 7.2 on multi-night hotel stays),
rerun agreement (28/30), latency (~35×) and cost (~390×). On the 7.2 cases the judge read "over $300 **a night**" and
divided $400 / 2 nights and $780 / 3 nights; the rule JSON compares the total amount, so gold and Z3 cite 7.2. The
judge's reading of the English is defensible; the schema has no per-night amount. That is a limit of the fact
schema, not of the judge, and we left gold as the rule JSON says.

**LLM facts + Z3** is the fairest comparison to our pipeline: same rules, same solver, only the reader differs. It
returned *undetermined* on two "sales kickoff" / "all-hands" flights where it gave `at_company_event` p = 0.75,
below the 0.85 threshold, where Jev gave ≥ 0.9. Its citations were perfect, like ours, because Z3 writes them.

**Keyword rules** fail where the README says they do: every intern/contractor rule (5.1–5.3) and every first-90-days
rule (10.1–10.3) is invisible to it, all 5 undetermined cases become violations, and the IRS coding checks misfire
whenever the memo has no keyword ("Round trip to Denver", "Marriott", "Zoom webinar add-on") or the meal is at a
company event (it cannot code `meals_100`).

**Caveats.** 107 cases built from 41 texts is small; the texts were used to tune Jev's question wording; the
structured contexts were assigned by this harness, not drawn from real ledgers; and the LLM rerun agreement rests
on 30 cases.
