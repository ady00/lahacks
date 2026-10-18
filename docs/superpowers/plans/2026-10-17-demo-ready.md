# Demo-ready in two hours

2026-10-17, late evening. Judges see the app at the 10:30 gate. Everything below was checked against a running local API and `pnpm build` at 22:30.

## What works today

- 245 API tests pass; `pnpm build` is clean; `node --test` on `web/lib` passes.
- `/check` runs the real engine with live Jev (`TYPESAFE_API_KEY` is set): the demo dinner comes back `violation` with the right facts, fix and explanation.
- Two-laptop flow exists end to end: sign in, check, Approvals page with Approve/Reject and 5 s refresh, case page flips, Authorize issues the mock card with a proof hash.
- Rules page lists the 16 company rules plus the IRS pack with the Z3 consistency check.

## What a judge would see broken

| Symptom | Cause | Fix size |
| --- | --- | --- |
| Case page opens with "The rule-by-rule graph is not available for this case. Try again" above everything | haogu's `PurchaseGraph` calls `GET /cases/{id}/graph` and `POST /cases/{id}/graph/preview`; neither route exists in `api/` on any branch | 5 min to hide, 45–60 min to build |
| Ledger shows "Audit of 1 transaction" and one row | API loads `data/transactions.csv`, `employees.csv`, `extractions.jsonl`; none exist. B's build writes `artifacts/backend/*.jsonl` in a different shape | 30 min |
| Evaluation page says "No results yet"; amber "Sample data" chip on every page | `/health.stub` is true whenever `eval/results.json` is missing. B's `evaluate` has not been run | 20 min, or 5 min fallback |
| Login dropdown shows "Unnamed · employee", "RevEmp", "Priya CFO" | leftover signup rows in the local `pop.db` (gitignored, so the deploy has its own) | 2 min |
| After 10 pm the dinner fires rule 6.1 too, so the card lists two violations | `hour` derives from the clock when no timestamp is given | demo at 10:30, no change |
| 16 web files, `api/cases.py`, `photon/` uncommitted | in-progress work on this machine | 10 min |

## Plan, in order

Stop at the line when the clock runs out; everything above it is a working demo.

### 0. Freeze what exists (10 min)

1. `pytest -q` and `cd web && pnpm build` once more; both are green now.
2. Stage and commit the pending work as two commits: `web/` polish, then `api/` + `photon/`. Plain messages, no trailer (repo rule). Push `main`.
3. Team chat to haogu: "Do you have `GET /cases/{id}/graph` on your machine? It is not on any branch and the case page shows the fallback." Their answer decides step 6.
4. Start `purchase-backend evaluate` in the background now (`GEMINI_API_KEY` is set). It feeds step 4.

### 1. Hide the graph panel when the API has no graph (5 min)

`web/components/PurchaseGraph.tsx:142`: when `initialGraph` is null, render `children` only and no message. The case page then opens on the verdict headline, the question or Authorize button, and the card. Keep the component so step 6 can light it up.

### 2. A ledger worth auditing (30 min)

Write `data/transactions.csv` (about 30 rows, company `demo`), `data/employees.csv` (Dana Ortiz manager, Jo Kim contractor, an intern, the new hire) and `data/approvals.csv` (two pre-approved rows). Realistic vendors and memos: `NOBU LA`, `UBER *TRIP`, `DELTA AIR`, `MARRIOTT`, `FIGMA`, `APPLE STORE`, `DOORDASH 11:40PM`. Plant the story:

- 20 compliant rows so the pie is not all red
- 3 over-$35 meals with no approval (rule 3.4)
- 1 contractor meal (5.1), 1 intern Uber not at an event (5.2)
- 1 $340 hotel night (7.2), 1 software buy (8.1)
- 2 meals coded `travel` so the IRS layer fires (`IRS-meal`)
- 2 rows with no amount keyword in the memo so Jev has to read them, and 1 late-night DoorDash for 6.1

Then `POST /data/reload`, open Ledger, and tune until `by_verdict` reads roughly 20 / 8 / 2 and `by_rule` lists five or six rules. Ledger column order is fine as is.

B's 31 real company-072 bills (insurance, rent, SaaS) have no employee link and no time, so they would all land `undetermined`. Leave them out of the demo ledger. Mention the 36,032-purchase build as the "real QuickBooks data" talking point instead.

### 3. Clean identity on the demo machines (2 min)

Delete `pop.db` and restart the API on each machine that will be shown, after step 2, so the dropdown shows only the seeded employees. Do the same on Vultr before the deploy check in step 5.

### 4. Evaluation page, or no Evaluation page (20 min)

If `artifacts/backend/evaluation/summary.json` landed from step 0: a 30-line script maps its four methods to the contract's four names (`Keyword rules`, `LLM judge`, `LLM facts + Z3`, `Jev + Z3`) and its `accuracy`, `median_latency_ms`, `cost_per_1000_usd` fields into `eval/results.json`. Missing metrics stay 0 and the page footnote says so. That also turns off the "Sample data" chip.

If it did not land: drop the Evaluation entry from `NAV` in `web/app/layout.tsx` and the chip with it. A judge never misses a page they did not know about; they do notice an empty one.

### 5. Rehearse, deploy, rehearse (25 min)

Local, two browser profiles: new hire checks the dinner, manager approves, new hire authorizes, Ledger shows the new row. Then deploy `main` to Vultr and the dashboard to Vercel, reset the Vultr `pop.db`, reload data, and run the same flow on the public URLs. Write the five-line script on an index card:

1. Check: "Client dinner Thursday with Acme's CFO, about $48." Needs approval. Point at the facts table: Jev read `meal`, `client present`; Z3 named rule 3.4 and the IRS coding.
2. Approvals on laptop two: Approve. Laptop one flips to compliant on its own.
3. Authorize card. Proof hash on screen: the limit traces back to the exact proof.
4. Ledger: N transactions audited in under a second, violations by rule.
5. Policy: every rule, and Z3 proved none of them conflict.

---- Working demo above this line ----

### 6. Stretch: light up the dependency graph (45–60 min)

Only if haogu does not have it. `GET /cases/{id}/graph` in a new `api/routes_graph.py`, shape from `web/lib/graph.ts`: one fact node per schema fact (known or not), one rule node per rule with `status` from the saved case (`violated` if in `violations`, `satisfied` if in `applied`, `uncertain` if a question names one of its facts, else `inactive`), condition and requirement text from `format.expr`'s inputs, edges fact→rule and rule→verdict. Skip `/graph/preview`; the "What if?" button only appears when a graph exists, so leave `editable_fields` empty and it stays hidden. This is the most visual thing in the product and the clearest "it is a proof, not a guess" moment.

### 7. Stretch: bank-rule checker form on the Policy page (30 min)

The API already answers `POST /bank-rules/check`. A native form with two prefilled QuickBooks rules (`UBER → Travel`, `UBER EATS 0–60 → Meals`) posting to `/act/bank-rules` and rendering `shadowed` and `overlaps`. On-theme for a QuickBooks dataset hackathon and it shows Z3 string theory doing something an accountant recognizes.

### 8. Stretch: manager approval by text

`photon/` is written and tested. Worth it only if the first live text round-trips on the first try during step 5; otherwise the Approvals page is the demo and Photon is a sentence in the pitch.

## Calls made here, say so if wrong

- Hide the graph rather than build it first. A blank panel costs nothing; a half-built one costs the headline.
- Hand-written demo ledger over B's real bills, for the reasons in step 2.
- Evaluation is cut before anything else is cut.
- No visual redesign. The pages are consistent and readable; the hour goes to data and the flow.
