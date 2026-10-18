# Proof of Purchase: Person C dashboard, 15:00 gate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Next.js app in `web/` with five routes — Check, Ledger, Rules, Evaluation, Approvals — each rendering the API's live stub JSON by 15:00, so the 20:00 work (Approve button, authorization card, question buttons) is adding server actions to pages that already exist.

**Architecture:** Every page is a React Server Component that `fetch`es the FastAPI server at `API_URL` on each request and renders the result; the Check form is a plain `<form method="get">` whose handler POSTs `/check` server-side and redirects to `/cases/[id]`, which renders the one `CaseCard` every other page reuses. No client components, no state, no API calls from the browser — the browser only ever talks to Next, so the Vercel-https → Vultr-http hop never hits mixed-content blocking.

**Tech Stack:** Next.js (App Router, whatever `create-next-app@latest` installs), TypeScript, Tailwind, pnpm. Types are generated once from the API's `openapi.json` with `openapi-typescript` (run via `pnpm dlx`, not a dependency). Tests: `pnpm build` (type-checks every page) plus `curl | grep` against the rendered HTML and one `node --test` file for the only pure logic.

**Spec:** `Proof of Purchase Build Guide.md` § "Person C: dashboard, approvals, deploy", *By 15:00*. Shapes: `API_CONTRACT.md` (tie-breaker is `{API_URL}/openapi.json`). Stub payloads the pages will show: `api/samples.py`.

**Not in this plan** (the other two 15:00 boxes and everything later): Vultr VM + Vercel deploy — separate plan; Approve button and live updates; authorization card; ledger filters/drawer; bank-rule checker UI; question buttons; Sentry; the eval chart; visual polish.

## Global Constraints

- Lane: Person C edits only `web/`. The one shared file C touches is `README.md`, append-only (a `## Dashboard` section). Never edit `api/`, `engine/`, `data/`, `extract/`, `eval/`, `agent/`.
- The API runs locally while building: from the repo root, `source .venv/bin/activate && uvicorn api.main:app --port 8000`. Every route answers sample JSON with header `X-Stub: 1`; `GET /health` reports `{"stub": true}`.
- `API_URL` is the only environment variable (same name as the contract's `.env` key). It is read in exactly one file, `web/lib/api.ts`, with default `http://localhost:8000`. **No `NEXT_PUBLIC_*` variables anywhere** — a browser-side call from the https Vercel site to `http://<VULTR_IP>:8000` is blocked as mixed content, so all API calls stay on the server.
- Every API `fetch` uses `cache: "no-store"` (stubs today, re-proven cases tomorrow; never a stale case).
- No client components (`"use client"`) at this gate. Forms are native `<form method="get">`. Server actions arrive at 20:00.
- No runtime dependencies beyond what `create-next-app` installs. `openapi-typescript` runs through `pnpm dlx` and its output `web/lib/openapi.d.ts` is committed; regenerate it whenever Person A announces a shape change.
- pnpm only (`pnpm-lock.yaml` committed; no `package-lock.json`).
- Field names are the contract's, verbatim: `verdict`, `facts[name].{value,source,p}`, `violations[].{rule,layer,text,because}`, `fix[].{fact,from,to}`, `questions[].{fact,text,p,options}`, `explanation`, `awaiting_approval`. Fact `p` is `null` for every non-Jev source; `fix` is `null` (no fix exists) or `[]` (nothing to fix) or a list.
- Money renders through one `Intl.NumberFormat` USD formatter (`$48.00`, `$12.50`); never string-concatenate `$`.
- Commits: plain messages, no co-author trailer (repo rule).

## Review Focus

1. **API unreachable** (uvicorn not started, wrong `API_URL`): the page must say "API unreachable at `<url>`", not a blank screen or a Next digest. → Task 1, `app/error.tsx`, tested in Task 1 Step 9.
2. **`fix: null` vs `fix: []`**: null means "no change you control makes this compliant" and must say so; `[]` renders nothing. The stub only sends a list, so this bites at 20:00 if untested. → Task 2, `fixLine` + `CaseCard`, tested in `lib/format.test.mjs`.
3. **`p: null` facts** (`amount`, `role`, `pre_approved`…) must render no percentage, never `NaN%` or `null%`. → Task 2, `pct`, tested in `lib/format.test.mjs`.
4. **`fix[].from: null`** (fact was unknown) must read "unknown → value", not "null → value". → Task 2, `fixLine`, tested in `lib/format.test.mjs`.
5. **Empty lists** — ledger with `transactions: []`, approvals with `cases: []`, and `/eval` before `eval/results.json` exists (the stub really does serve `{"as_of": null, "n_heldout": 0, "systems": []}`, so the header must not print "As of null"): each page shows a one-line empty state rather than an empty table. → Tasks 3, 5, 6; the eval empty state is live-tested in Task 5 Step 2, the other two have a grep-able string checked by reading the page component (those stubs cannot return empty).

---

### Task 1: Scaffold `web/`, API client, generated types, nav, error page

**Files:**
- Create: `web/` via `create-next-app` (package.json, tsconfig.json, `app/layout.tsx`, `app/globals.css`, `app/page.tsx`, `.gitignore`, …)
- Create: `web/.env.local` (gitignored by the scaffold), `web/lib/api.ts`, `web/lib/openapi.d.ts` (generated), `web/lib/types.ts`, `web/app/error.tsx`
- Modify: `web/app/layout.tsx`, `web/app/page.tsx`
- Modify (append): `README.md`

**Interfaces:**
- Consumes: the running API at `http://localhost:8000` (`/health`, `/openapi.json`).
- Produces, for every later task:
  - `web/lib/api.ts`: `export async function get<T>(path: string): Promise<T>` and `export async function post<T>(path: string, body?: unknown): Promise<T>`. Both: `fetch(`${API_URL}${path}`, { cache: "no-store", method, headers: {"content-type": "application/json"}, body: JSON.stringify(body) })`; on `!res.ok` throw `new Error(`${method} ${path} → ${res.status}: ${await res.text()}`)`; on network failure (fetch rejects) throw `new Error(`API unreachable at ${API_URL}`)`. `export const API_URL = process.env.API_URL ?? "http://localhost:8000"`.
  - `web/lib/types.ts`: `import type { components } from "./openapi"; type S = components["schemas"]; export type Case = S["Case"]; export type CaseList = S["CaseList"]; export type Authorization = S["Authorization"]; export type LedgerOut = S["LedgerOut"]; export type LedgerRow = LedgerOut["transactions"][number]; export type AuditSummary = S["AuditSummary"]; export type PolicyOut = S["PolicyOut"]; export type PolicyAudit = S["PolicyAudit"]; export type EvalOut = S["EvalOut"]; export type Health = S["Health"]; export type FixStep = NonNullable<Case["fix"]>[number]; export type Fact = Case["facts"][string];`
  - `web/app/layout.tsx`: nav links in this order and with these labels: `Check → /check`, `Ledger → /ledger`, `Rules → /rules`, `Evaluation → /eval`, `Approvals → /approvals`; and an amber `STUB DATA` badge beside the title when `GET /health` returns `stub: true` (the layout is itself an async server component; if `/health` throws, render no badge rather than failing the whole shell — wrap that one call in `try/catch`).

- [ ] **Step 1: Start the API and confirm the stub answers**

Run from the repo root: `source .venv/bin/activate && uvicorn api.main:app --port 8000 &` then `curl -si localhost:8000/health`
Expected: `HTTP/1.1 200`, `x-stub: 1`, body ends with `"stub":true}` (`policy_version` is the real 12-hex hash of the rule packs, not the stub constant — `/health` is the one route that already reads the engine).

- [ ] **Step 2: Scaffold the app**

Run from the repo root: `pnpm create next-app@latest web --ts --tailwind --eslint --app --no-src-dir --import-alias "@/*" --use-pnpm` (accept defaults for anything else it asks; if it asks about Turbopack or React Compiler, take the default).
Then: `cd web && pnpm dev &` and `curl -s -o /dev/null -w '%{http_code}\n' localhost:3000/`
Expected: `200`

- [ ] **Step 3: Generate the types from the API schema**

Run from `web/`: `pnpm dlx openapi-typescript http://localhost:8000/openapi.json -o lib/openapi.d.ts`
Expected: file created; `grep -c '"Case":' lib/openapi.d.ts` prints `1`, and `grep -E '"(CaseList|LedgerOut|AuditSummary|PolicyOut|PolicyAudit|EvalOut|Health|Authorization)":' lib/openapi.d.ts | wc -l` prints `8`.

- [ ] **Step 4: Write `web/lib/types.ts` and `web/lib/api.ts`** with the exact exports in the Interfaces block above. `web/.env.local` contains one line: `API_URL=http://localhost:8000`.

- [ ] **Step 5: Write `web/app/layout.tsx`** — `<html><body>` with a top nav (`<nav>` of `<Link>`s in the order above), the title "Proof of Purchase", the conditional `STUB DATA` badge, and `{children}` inside `<main className="mx-auto max-w-5xl p-6">`. Delete the scaffold's starter markup from `app/page.tsx` and replace it with `import { redirect } from "next/navigation"; export default function Home() { redirect("/check"); }`.

- [ ] **Step 6: Write `web/app/error.tsx`** — the scaffold-standard client error boundary (`"use client"` is required by Next for this one file and is the sole exception to the no-client rule): renders `<h1>Something broke</h1><p>{error.message}</p>` and a `<button onClick={reset}>Retry</button>`. Next only passes `error.message` through to the client in dev; in production it is replaced by a digest, so also log it: `useEffect(() => console.error(error), [error])`.

- [ ] **Step 7: Build and type-check**

Run from `web/`: `pnpm build`
Expected: exits 0; the route table lists `/`, `/check` is not yet there (Task 2 adds it) — only `/` and `/_not-found` appear. No type errors.

- [ ] **Step 8: Verify the shell**

Run: `curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' localhost:3000/`
Expected: `307 http://localhost:3000/check`
Run: `curl -s localhost:3000/ledger | grep -o 'STUB DATA'` (the 404 page still renders the layout)
Expected: `STUB DATA`

- [ ] **Step 9: Verify the unreachable-API message** (Review Focus 1)

Stop uvicorn (`kill %1` or ctrl-C in its terminal). In the browser open `http://localhost:3000/` — the nav renders with **no** badge (layout swallowed the `/health` error). Restart uvicorn afterwards: `uvicorn api.main:app --port 8000 &`. (Full-page errors are exercised in Task 2 Step 9, once a page fetches.)

- [ ] **Step 10: Append to `README.md`** a `## Dashboard` section: how to run (`cd web && pnpm install && pnpm dev`), the one env var `API_URL`, and the regenerate-types command from Step 3.

- [ ] **Step 11: Commit**

```bash
git add web README.md
git commit -m "feat(web): scaffold Next.js dashboard with API client and generated types"
```

---

### Task 2: `CaseCard`, format helpers, Check page, `/cases/[id]`

**Files:**
- Create: `web/lib/format.ts`, `web/lib/format.test.mjs`, `web/components/VerdictChip.tsx`, `web/components/CaseCard.tsx`, `web/app/check/page.tsx`, `web/app/cases/[id]/page.tsx`

**Interfaces:**
- Consumes: `get`, `post` from `lib/api.ts`; `Case`, `FixStep`, `Fact` from `lib/types.ts`.
- Produces:
  - `web/lib/format.ts`: `export const usd = (n: number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n)`; `export function pct(p: number | null | undefined): string` → `"97%"` for `0.97` (rounded to whole percent), `""` for null/undefined; `export function fixLine(s: FixStep): string` → for `fact === "amount"`: `` `amount: keep it at or under ${usd(to)}` ``; otherwise `` `${fact}: ${from ?? "unknown"} → ${to}` `` with booleans rendered as `true`/`false`.
  - `web/components/VerdictChip.tsx`: `export function VerdictChip({ verdict }: { verdict: Case["verdict"] })` — a rounded pill, `bg-green-100 text-green-800` for `compliant`, `bg-red-100 text-red-800` for `violation`, `bg-amber-100 text-amber-800` for `undetermined`, text is the verdict word.
  - `web/components/CaseCard.tsx`: `export function CaseCard({ c }: { c: Case })` — renders, top to bottom: `<VerdictChip>` + `case_id` + `employee_id`; the request `text`; `explanation` in a highlighted paragraph; a **Facts** table with columns Fact · Value · Source · p (`pct(f.p)`); **Violations** list: `rule` (bold) `layer` (muted) `text`, then `because: a, b` muted; **Fix**: `null` → the sentence `No change you control makes this compliant.`, `[]` → render nothing, list → `<ul>` of `fixLine`; **Questions**: `<ol>` of `q.text` with `options` joined by ` / ` when non-null (buttons come at 20:00); `awaiting_approval` true → an amber line `Waiting for manager approval`. Later tasks reuse `CaseCard` unchanged.
  - Route `GET /cases/[id]` renders `CaseCard` for `get<Case>(`/cases/${id}`)`.
  - Route `GET /check` renders the form; `GET /check?text=…&employee_id=…[&amount=…]` POSTs `/check` and redirects to `/cases/{case_id}`.

- [ ] **Step 1: Write the failing test `web/lib/format.test.mjs`**

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { pct, fixLine, usd } from "./format.ts";

test("pct renders Jev probabilities and nothing for null", () => {
  assert.equal(pct(0.97), "97%");
  assert.equal(pct(0.08), "8%");
  assert.equal(pct(null), "");
  assert.equal(pct(undefined), "");
});

test("fixLine: boolean, enum, unknown-from, amount", () => {
  assert.equal(fixLine({ fact: "pre_approved", from: false, to: true }), "pre_approved: false → true");
  assert.equal(fixLine({ fact: "coded_account", from: "travel", to: "meals_50" }), "coded_account: travel → meals_50");
  assert.equal(fixLine({ fact: "receipt_attached", from: null, to: true }), "receipt_attached: unknown → true");
  assert.equal(fixLine({ fact: "amount", from: 48, to: 35 }), "amount: keep it at or under $35.00");
});

test("usd", () => {
  assert.equal(usd(48), "$48.00");
  assert.equal(usd(12.5), "$12.50");
});
```

- [ ] **Step 2: Run it to verify it fails**

Run from `web/`: `node --test lib/format.test.mjs`
Expected: FAIL — `Cannot find module './format.ts'`

- [ ] **Step 3: Implement `web/lib/format.ts`** with the three exports in the Interfaces block. (Node 26 strips the types at runtime; no build step.)

- [ ] **Step 4: Run the test to verify it passes**

Run: `node --test lib/format.test.mjs`
Expected: `# pass 3`, `# fail 0`

- [ ] **Step 5: Write `VerdictChip.tsx` and `CaseCard.tsx`** per the Interfaces block.

- [ ] **Step 6: Write `web/app/cases/[id]/page.tsx`** — async server component: `const c = await get<Case>(`/cases/${params.id}`)` (in current Next, `params` is a Promise: `const { id } = await params`), returns `<CaseCard c={c} />`.

- [ ] **Step 7: Write `web/app/check/page.tsx`** — async server component taking `searchParams`. If `text` and `employee_id` are present: `const c = await post<Case>("/check", { text, employee_id, amount: amount ? Number(amount) : undefined })` then `redirect(`/cases/${c.case_id}`)`. Otherwise render `<form method="get">` with: `<textarea name="text">` prefilled `Client dinner Thursday with Acme's CFO, about $48.`; `<select name="employee_id">` with options `e_newhire` (selected), `e_intern`, `e_contractor`; `<input name="amount" type="number" step="0.01" min="0.01">` (optional); submit button `Check`. Native validation only (`required` on text and employee_id). Amount is optional per the contract (the server takes the first `$…` in the text).

- [ ] **Step 8: Verify the flow**

Run from `web/`: `pnpm build` → exits 0, route table shows `/check` and `/cases/[id]`.
Run: `curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' 'localhost:3000/check?text=Client+dinner&employee_id=e_newhire&amount=48'`
Expected: `307 http://localhost:3000/cases/c_8f2a1b3c`
Run: `curl -s localhost:3000/cases/c_8f2a1b3c | grep -oE 'violation|rule 3\.4|97%|meals_50|pre_approved: false → true|Waiting for manager approval' | sort -u`
Expected (all six lines, any order): `97%`, `Waiting for manager approval`, `meals_50`, `pre_approved: false → true`, `violation`, `rule 3.4`
Run: `curl -s localhost:3000/cases/c_8f2a1b3c | grep -c 'null%\|NaN%'`
Expected: `0`

- [ ] **Step 9: Verify the unreachable-API page** (Review Focus 1)

Stop uvicorn, then `curl -s -o /dev/null -w '%{http_code}\n' localhost:3000/cases/c_8f2a1b3c` → `500` (not `200` with an empty body), and in the browser the page shows `API unreachable at http://localhost:8000` with a Retry button. Restart uvicorn.

- [ ] **Step 10: Commit**

```bash
git add web
git commit -m "feat(web): check form, case page and CaseCard rendering the contract case"
```

---

### Task 3: Ledger page

**Files:**
- Create: `web/app/ledger/page.tsx`

**Interfaces:**
- Consumes: `get<LedgerOut>("/ledger")`, `post<AuditSummary>("/ledger/audit", { company: "demo" })`, `VerdictChip`, `usd`.
- Produces: route `GET /ledger`. Both fetches run in parallel (`Promise.all`).

- [ ] **Step 1: Write the page** — top: an **Audit** strip from the summary: `n` transactions, three counts from `by_verdict` each beside its `VerdictChip`, `elapsed_ms`, then `by_rule` as `rule — text — count`. Below: a table of `transactions` with columns Txn · Vendor · Memo · Amount (`usd`) · Timestamp · QB category · Coded account · Verdict (`VerdictChip`) · Rules (`violations.join(", ")`); the `txn_id` cell is a `<Link href={`/cases/${row.case.case_id}`}>` (the detail drawer at 02:00 reuses `CaseCard` through this route). If `transactions.length === 0` render the line `No transactions loaded yet.` instead of the table. Footer line `Showing {transactions.length} of {total}`.

- [ ] **Step 2: Verify**

Run: `curl -s localhost:3000/ledger | grep -oE 't_000412|Nobu|\$210\.00|1061|142|href="/cases/c_8f2a1b3c"|Showing 1 of 1' | sort -u | wc -l`
Expected: `7`
Run: `grep -c 'No transactions loaded yet' app/ledger/page.tsx` → `1` (Review Focus 5)

- [ ] **Step 3: Commit**

```bash
git add web/app/ledger
git commit -m "feat(web): ledger page with audit summary"
```

---

### Task 4: Rules page

**Files:**
- Create: `web/app/rules/page.tsx`

**Interfaces:**
- Consumes: `get<PolicyOut>("/policy")`, `post<PolicyAudit>("/policy/audit")` in parallel.
- Produces: route `GET /rules`.

- [ ] **Step 1: Write the page** — header line `Policy version {version}`. **Rules**: one row per rule, left column `id` (bold) and `layer` (muted), middle the sentence `text`, right a `<pre className="text-xs">` of `JSON.stringify({ when: rule.when, require: rule.require }, null, 1)` ("each rule beside its sentence"). **Policy audit**: `Dead rules:` followed by `dead.join(", ")` or `none`; `Conflicts:` a list of `a` × `b` with the `example` fact map rendered as `key=value` pairs, or `none`. **Facts** (from `facts`): a compact table Fact · kind · values/`mutable`. Bank-rule checker UI is 02:00 — not here.

- [ ] **Step 2: Verify**

Run: `curl -s localhost:3000/rules | grep -oE 'stub00000000|5\.2|Interns get no transport|9\.9|6\.1|expense_kind=meal' | sort -u | wc -l`
Expected: `6`

- [ ] **Step 3: Commit**

```bash
git add web/app/rules
git commit -m "feat(web): rules page with policy audit"
```

---

### Task 5: Evaluation page

**Files:**
- Create: `web/app/eval/page.tsx`

**Interfaces:**
- Consumes: `get<EvalOut>("/eval")`.
- Produces: route `GET /eval`.

- [ ] **Step 1: Write the page** — the stub serves `{"as_of": null, "n_heldout": 0, "systems": []}` until Person B writes `eval/results.json`, so the empty state is the one the 15:00 gate will show. If `systems.length === 0` render only the line `No evaluation results yet.` (Review Focus 5). Otherwise: header `As of {as_of} · {n_heldout} held-out transactions`, then one table, one row per entry of `systems` in the order served, columns: System · Accuracy · Citation F1 · Rerun agreement · Median latency (ms) · Cost / 1k (USD) · Questions / txn. Accuracy, F1 and rerun agreement render through `pct`; latency as an integer; cost via `usd`; questions to two decimals. Highlight the `Jev + Z3` row (`font-semibold bg-green-50`). The chart is a later gate.

- [ ] **Step 2: Verify the empty state**

Run: `curl -s localhost:3000/eval | grep -c 'No evaluation results yet'`
Expected: `1`

- [ ] **Step 3: Verify the populated table** — `eval/` is Person B's folder: write this file locally, never commit it, and delete it in the last command.

Run from the repo root (the API picks the file up on the next request; no restart):
```bash
cat > eval/results.json <<'EOF'
{"as_of": "2026-10-18T09:40:00-07:00", "n_heldout": 150,
 "systems": [{"name": "Keyword rules", "accuracy": 0.61, "citation_f1": 0.42, "rerun_agreement": 1.0, "median_latency_ms": 2, "cost_per_1k_usd": 0.0, "questions_per_txn": 0.0},
             {"name": "Jev + Z3", "accuracy": 0.94, "citation_f1": 0.91, "rerun_agreement": 1.0, "median_latency_ms": 140, "cost_per_1k_usd": 0.32, "questions_per_txn": 0.18}]}
EOF
curl -s localhost:3000/eval | grep -oE 'Keyword rules|Jev \+ Z3|94%|140|\$0\.32|150 held-out' | sort -u | wc -l
rm eval/results.json; git status --short eval
```
Expected: `6`, then no output from `git status` (nothing left in `eval/`).

- [ ] **Step 4: Commit**

```bash
git add web/app/eval
git commit -m "feat(web): evaluation page"
```

---

### Task 6: Approvals tab stub

**Files:**
- Create: `web/app/approvals/page.tsx`

**Interfaces:**
- Consumes: `get<CaseList>("/cases?awaiting_approval=true")`, `usd`, `VerdictChip`.
- Produces: route `GET /approvals`. The 20:00 Approve button becomes a server action on this page; nothing here needs to change for it.

- [ ] **Step 1: Write the page** — header `Pending approvals ({cases.length})`. For each case: a card with `employee_id`, the request `text`, `usd(Number(c.facts.amount.value))` when `c.facts.amount` exists (a fact `value` is typed as the union of every fact type, hence the `Number`), the cited rules (`violations.map(v => `${v.rule}: ${v.text}`)`), and a `<Link href={`/cases/${case_id}`}>` labelled `Open case`. If `cases.length === 0` render `Nothing waiting for approval.` (Review Focus 5).

- [ ] **Step 2: Verify**

Run: `curl -s localhost:3000/approvals | grep -oE 'Pending approvals \(1\)|e_newhire|\$48\.00|3\.4: Any expense over|href="/cases/c_8f2a1b3c"' | sort -u | wc -l`
Expected: `5`

- [ ] **Step 3: Full gate check**

Run from `web/`: `pnpm build && node --test lib/format.test.mjs && grep -rn NEXT_PUBLIC app lib components; echo "grep exit $?"`
Expected: build exits 0, `# fail 0`, and the grep prints nothing with `grep exit 1` (no browser-side env var; Global Constraints).
Then, with uvicorn running: `for p in check ledger rules eval approvals; do printf '%s ' $p; curl -s -o /dev/null -w '%{http_code}\n' localhost:3000/$p; done`
Expected: five lines, all `200`.

- [ ] **Step 4: Commit**

```bash
git add web/app/approvals
git commit -m "feat(web): approvals tab listing pending cases"
```

---

## Hand-off to the next gates

- **Deploy (second 15:00 box):** `web/` is Vercel-ready as is — import the repo, set Root Directory `web`, add env `API_URL=http://<VULTR_IP>:8000`. Nothing in the pages changes.
- **20:00:** `/cases/[id]/page.tsx` gets two server actions (`answer(fact, value)` → `POST /cases/{id}/answer`, and `authorize()` → `POST /cases/{id}/authorize`) that call `revalidatePath` and re-render the same `CaseCard`; the approvals page gets an `approve(case_id)` action the same way, and `export const revalidate = 0` plus a `<meta httpEquiv="refresh" content="5">` is the zero-JS way to "update live".
- **02:00:** ledger filters are `?company=&verdict=` passed straight through to `/ledger` plus a `<form method="get">` with a `<select name="verdict">`; the detail drawer is a `<details>` wrapping `<CaseCard c={row.case} />`.
