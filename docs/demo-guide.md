# Proof of Purchase: using the site to its fullest

For whoever is driving the demo. Two browser profiles (or two laptops) make the approval moment land; one works for everything else.

## Setup, once

```bash
# API, from the repo root
source .venv/bin/activate
.venv/bin/python -m uvicorn api.main:app --port 8000      # loads data/*.csv on start; live Jev when TYPESAFE_API_KEY is set

# Dashboard
cd web && pnpm dev                                        # API_URL defaults to http://localhost:8000
```

Checks before anyone watches: `curl localhost:8000/health` answers; the Ledger page says "Audit of 34 transactions" or more; the Sign in dropdown lists Sam Lee, Ria Patel, Jo Kim, Dana Ortiz and nothing odd. If the ledger is empty, `curl -X POST localhost:8000/data/reload`.

## Who to sign in as

| Account | Why it matters |
| --- | --- |
| Sam Lee, employee | The new hire. Every ordinary rule applies. |
| Ria Patel, intern | Interns get no transport or meals outside company events (rules 5.2, 5.3). |
| Jo Kim, contractor | Contractors are never reimbursed for meals (rule 5.1). The fix comes back null: nothing the person controls makes it compliant. |
| Dana Ortiz, tick "I approve purchases" | The manager. Only this flag shows the Approvals page. |

Sign-in is a cookie, no password. Use one profile per person so both stay signed in.

## The main flow (four minutes)

1. **Check a purchase** as Sam: "Client dinner Thursday with Acme's CFO, about $48." The headline says it needs manager approval. Scroll the card: Jev read `meal` and `client present` with its confidence, Z3 names rule 3.4 and the facts that decided it, and the IRS layer already coded it `meals_50`.
2. **Why the rules decided this** sits under the card. Red wires are the facts in the unsat core; gray rules never fired. Tick "Show all rules" to make the point that every rule ran. Click a rule to isolate its wires.
3. **What if?** on the same panel. Tick `Pre-approved`, choose true, Preview changes. The hypothetical verdict flips to compliant without saving anything; the real buttons stay paused until Reset. Try `Amount` at 34 for a second route to compliant, or clear `Expense kind` to watch it go undetermined and ask a question.
4. **Approvals** as Dana on the other profile. The case is already there; the list refreshes itself every five seconds. Approve.
5. Back on Sam's tab, the page has flipped to "You can buy this." **Authorize card** issues the mock card: limit, merchant category code, expiry, and a proof hash that is the SHA-256 of the facts, policy version and verdict.
6. **Ledger** now has one more row, Sam's dinner, verdict compliant, next to the 33 seeded transactions.

## Second-best moments, pick by audience

- **Ledger audit.** 33 real-looking QuickBooks rows decided in under 100 ms, with violations grouped by rule: pre-approval, a contractor lunch, an intern's Uber, a hotel over $300, Adobe without IT approval, a 11:40 pm DoorDash, a team outing that is never reimbursed, and a company-event lunch coded 50% that should be 100% deductible (an IRS note in amber, counted in the summary). Click any transaction id to open its full case and graph.
- **Undetermined, honestly.** Dana's "Team lunch after the sprint review" is the one undetermined row: Jev was 83% sure it was a company event, below the 85% bar, so the system asks instead of guessing.
- **Policy page.** Every company and IRS rule with its condition in plain words, then the consistency check: Z3 proved no rule is dead and no two rules contradict each other.
- **IRS page.** What the tax treatment on a case means: the six accounts, the four deductibility values, and the thirteen cited rules behind them. Say "company policy decides; the IRS layer only annotates." Then the switch: turn it off, check the client dinner again (same verdict, no account, no deductibility), turn it back on. Good typed checks: "Lakers tickets with the Acme team, $340" (entertainment, 0% deductible) and "Drove 120 miles to the client site, $95" (allowed by policy, with an IRS note that the amount above 72.5¢ a mile is wages).
- **Questions instead of hallucination.** As Sam, check "Team lunch after the sprint review, $33." Jev is only 69% sure it was a company event, so the verdict is undetermined and one question appears: "Was this at a company-wide event?" Answer with a button and the rules re-check instantly. Yes makes it a 100% deductible event meal; no makes it a plain compliant meal.
- **A contractor meal** as Jo: "Lunch between client meetings, $19." The answer is a violation with no fix, because the only fact that would help is the role, and nobody can change that.
- **An amount question.** "Uber to the airport" with no number: the rideshare rule depends on the amount, so the system asks for it before deciding.
- **Always needs approval.** "Flight to the Denver summit" with or without a number: airfare needs pre-approval at any price (rule 7.1), so the verdict is a violation whose fix is manager approval.

## Things to avoid on stage

- After 10 pm local time a meal with no timestamp also trips rule 6.1 (meals after 10 pm), so the card lists two violations. Fine as a talking point, confusing as an opener. The seeded dinner avoids it because its time is explicit; a typed check uses the clock.
- The Evaluation page is real now: 107 held-out purchases, four systems. Read the Jev + Z3 row off the screen and name a miss before the judge asks. If the amber "Sample data" chip shows in the header, `eval/results.json` is missing on that machine.
- Clicking Approve twice is harmless. Replaying Authorize on a violation returns a 409 and an error page.

## Where the data comes from

`data/transactions.csv`, `employees.csv`, `approvals.csv` are the seed ledger; `data/extractions.jsonl` holds the live Jev reading of each memo, generated once so the ledger does not re-call the model. Edit the CSV and `POST /data/reload` to change the story. Verdicts cache per policy version, so editing a rule in `engine/` re-audits everything on the next ledger load.
