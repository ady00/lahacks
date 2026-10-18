# apriori · pitch notes for the Intuit and Workday tables

For whoever is talking. One product, two framings. Say the 30-second core first, then switch to the track the judge is from. Numbers marked **[eval]** come from the Evaluation page; read them off the screen rather than from memory.

## The 30-second core (both tracks)

"A new hire types *'Client dinner Thursday with Acme's CFO, about $48'* and gets a proven answer in under a second: allowed, not allowed with the exact rule and the cheapest fix, or one question that decides it. A small typed model reads the sentence into facts with calibrated probabilities. Z3, a theorem prover, checks those facts against every company and IRS rule at once. A manager approves on the dashboard or by text message, a card authorization is issued for exactly that amount with a hash of the proof, and the same rules audit the whole QuickBooks ledger."

Then the one line that makes people lean in: **"The model never decides anything. It only reads. Everything that decides is a proof you can inspect."**

## Live demo path (four minutes)

1. Sign in as Sam Lee (new hire, 26 days in). Home page shows "3 first-90-days rules apply to you for 64 more days" with a link to **What applies to you**.
2. Check "Client dinner Thursday with Acme's CFO, about $48." Verdict: needs manager pre-approval (rule 3.4). Point at the facts table: which came from the model (with its confidence), which from the employee record, which from the clock.
3. Scroll to the dependency graph. Red wires are the unsat core. Tick *Show all rules*: all 27 ran. Use **What if?** to flip pre-approved and watch it go compliant without saving.
4. Approve as Dana on the other profile. Sam's page flips on its own. **Authorize card**: limit $48, MCC 5812, 24-hour expiry, proof hash.
5. Ledger: the new row sits next to 33 seeded QuickBooks-shaped rows, all audited by the same rules in milliseconds.
6. Pick one closer by audience (below).

## Intuit table: QuickBooks, System One models

What their brief asks for: a technical unlock from System One, clear customer value, and a realistic evaluation against classical ML and LLM baselines.

**Technical unlock.** Jev answers three typed questions per purchase in about 100 ms with calibrated probabilities, so we can afford to read every transaction and every policy sentence, and we can refuse to turn a 0.6 into a fact. That is what lets a solver sit downstream: unknown facts stay free variables and the verdict becomes *undetermined* instead of wrong. An LLM judge cannot do that reliably and costs dollars per thousand checks; keyword rules cannot say "I don't know" at all.

**Customer value, in QuickBooks vocabulary.**
- Pre-spend control: the check happens before the card is swiped, which Intuit Assist does not do today. The authorization carries the exact limit and merchant category.
- Correct coding on the way in: the IRS layer derives the account (meals 50%, meals at a company event 100%, entertainment 0%) from the same proof, so the ledger arrives coded.
- Ledger audit: every posted transaction re-judged by the live policy, violations grouped by rule, in about a millisecond per row.
- **Bank rules page**: paste QuickBooks' own bank rules (description contains words, amount in range, first match wins). Z3 string theory finds rules that can never fire because an earlier rule shadows them, and pairs that overlap, with a concrete example transaction. That is a QuickBooks-native bug finder nobody has.
- Policy Studio: a sentence becomes a rule, proven consistent with the other 27 before it is saved.

**Evaluation (the Evaluation page).** Four systems on the same held-out purchases with human-labeled facts: Keyword rules, LLM judge, LLM facts + Z3, Jev + Z3. Scored on verdict accuracy, rule-citation F1, rerun agreement, median latency, cost per 1,000 checks and questions asked. Read the row for Jev + Z3 off the screen **[eval]**, then say where it loses (the README in `eval/` names the cases). Judges trust an evaluation that admits a weakness; volunteer it before they ask.

**Say about the data.** The demo ledger is 33 hand-written rows planted so every rule fires at least once. Intuit's 100-company archive is ingested separately into 36,032 purchase cases by the offline loader, with every change disclosed in `docs/backend.md`. The held-out evaluation set and how its labels were made are in `eval/README.md`.

**If they ask about a real QuickBooks connection.** It is designed, not built: `docs/quickbooks-integration.md` maps Purchase fields to our ledger columns, lists the OAuth flow, rate limits and write-back, and estimates about four hours for a read-only sandbox sync and about five and a half with write-back of the account and proof note. Everything downstream of the CSV already exists, so nothing in the engine changes.

**Likely questions.**
- *Why not just prompt an LLM with the policy?* It gives a different answer tomorrow, invents rule numbers, and cannot prove two rules conflict. The LLM judge row on the Evaluation page is that system; point at its rerun agreement and cost.
- *Why Z3 and not if/else?* The if/else version is in the repo as the keyword baseline. It cannot say undetermined, cannot cite which facts decided a verdict, cannot compute a fix, and cannot prove the policy is consistent. Same 27 rules as data drive the check, the fix, the question, the audit and the graph.
- *What does System One add over a small classifier?* Calibration and typed questions with no training set per company: the three questions are prompts, so a new policy fact is one more question, not a new model.

## Workday table: Build the Future of Work with AI

What their rubric weighs: agentic logic 30%, new-hire relevance 20%, responsible AI and trust 20%, Workday relevance 15%, UX and inclusivity 10%, pitch 5%.

**Frame it as the onboarding buddy for the one task every new hire gets wrong first: spending company money.** Nobody reads the expense policy. Sam has been here 26 days, has a corporate card, and is about to buy a monitor.

**Agentic logic (30%).** It does not just answer; it moves the person to the next step.
- Plans: reads intent into facts, proves the verdict, computes the cheapest fix the person controls (MaxSAT), or the single question that decides it.
- Prepares the action: puts the case on the manager's Approvals page with the rule that put it there; the manager can approve from the dashboard or by replying YES to a text.
- Executes safely: the card authorization is issued only on a compliant proof, for exactly that amount and merchant category, and expires in 24 hours.
- Re-proves on every change: an answer, an approval, a policy edit. Nothing is patched locally.

**New-hire relevance (20%).**
- **What applies to you**: a personal policy briefing proven from the rule set for Sam's role and tenure. Z3 says which rules can never fire for Sam and which first-90-days rules apply, with a countdown ("for 64 more days"). No model writes it.
- Tenure is a fact from the employee record: the first-90-days rules (equipment and hotels need pre-approval at any price, no entertainment) apply to Sam and not to Dana, automatically.
- Role rules for interns and contractors show the same mechanism for other early-career populations.

**Responsible AI and trust (20%).** Walk the rubric's own list, on screen.
- *What the AI is doing*: the facts table says which facts the model read, with its confidence; everything else came from records or the clock.
- *Why it recommended this*: the unsat core names the exact facts that decided each broken rule; the graph shows every rule that ran.
- *What it will not do*: it never decides employment, pay or access; a purchase that a rule says needs approval always waits for a human manager; a card is never authorized on a non-compliant proof.
- *What happens when it is uncertain*: a probability between 0.15 and 0.85 is not a fact. The verdict becomes undetermined and the person is asked one question, not guessed at.
- *How the user corrects it*: answer the question, use What if?, or edit the policy in plain English and have it re-proven against the rest.
- *Privacy*: the only personal data used is the employee record (role, title, department, start date, manager). No chat history, no free text leaves the company except the purchase sentence sent to the reading model.
- *Fairness*: the same rules run for everyone; a rule that singles out a role is visible in the policy, in the person's briefing, and in the consistency check.

**Workday relevance (15%).** The employee record is Worker-shaped: job title, department, level, location, start date, manager. Map the flow to Workday objects when you say it: our pre-approval is a Spend Authorization, our authorized purchase is an Expense Report line arriving already coded and already proven. Tenure-based rules are a workforce decision made transparent. We did not build inside Workday, which their brief says is fine; the record shape is the integration point.

**UX and inclusivity (10%).** Plain language in, plain language out. No policy jargon is required to ask. Explanations are templated from the proof, so they read the same for everyone. Works by text message for a manager who is not at a desk.

**Pitch (5%).** Problem: new hires spend wrong and find out at reimbursement time. Solution: ask first, get a proof. Impact: fewer rejected expenses, less manager time, a ledger that is already audited.

**Likely questions.**
- *Where is the human in the loop?* Every approval. The agent prepares the case; a named manager decides; the decision is recorded with their id and time, and the case is re-proven with it.
- *What is autonomous?* Reading, proving, the fix, the question, coding the account, and the card authorization once the proof is compliant. Nothing involving another person's judgment.
- *Could this be unfair to new hires?* The first-90-days rules are company policy made visible; the person sees them on day one with the date they stop applying, instead of discovering them at reimbursement.
- *What about Workday Expenses?* Same objects, earlier in time: we move the policy check from after the spend to before it.

## Numbers to have ready

| Fact | Value |
| --- | --- |
| Rules in the live policy | 27 (16 company, 3 first-90-days, 8 IRS) plus any added in Policy Studio |
| Facts the rules see | 11, of which 3 come from the model and 8 from records, the clock or the rules |
| Model latency per purchase | about 100 ms (Jev, three typed questions) |
| Solve time per purchase | about 1 ms; the 33-row ledger audits in a few ms |
| Held-out evaluation cases | **[eval]** |
| Jev + Z3 accuracy / citation F1 / rerun agreement | **[eval]** |
| LLM judge rerun agreement and cost per 1,000 | **[eval]** |
| Intuit archive ingested offline | 36,032 purchase cases, 100 companies |

## Do not say

- "The AI decides." It reads. Z3 decides.
- "100% accurate." Read the Evaluation page and name the misses.
- "Integrated with QuickBooks / Workday." Designed for, shaped like, not connected. The integration doc has the plan and the hours.
