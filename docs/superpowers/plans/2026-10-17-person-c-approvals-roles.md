# Proof of Purchase: roles, approvals and the 20:00 case actions — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Two people on two laptops: a new hire signs up, checks a purchase and watches their case page; a manager signs up on another machine, sees the case on Approvals, clicks Approve, and the new hire's page flips to compliant with an Authorize button that issues the mock card — all state in the one API.

**Architecture:** Identity is a dashboard-only cookie `pop_user` (`{employee_id, name, manager}`); signup creates a real employee row through a new `POST /employees` so `/check` accepts the id. Every mutation is a native `<form method="post">` to one route handler, `app/act/[name]/route.ts`, which calls the API and 303-redirects — no client JS, every action curl-testable. Pages that wait on someone else (`/cases/[id]` while `awaiting_approval`, `/approvals`) reload themselves with `<meta http-equiv="refresh">`. `cases.authorize` on `main` already upserts the case into `transactions`, so the Ledger page shows an authorized purchase with no further work.

**Tech Stack:** FastAPI + sqlite3 (`api/`), Next.js 16 App Router + Tailwind (`web/`), pytest, `node --test`, curl.

**Spec:** `Proof of Purchase Build Guide.md` § Person C *By 20:00* (Check page question buttons; Approvals tab with Approve calling `/approve`, updating live; authorization card) plus the brainstorm in this conversation: simple signup, roles, different laptops. Shapes: `API_CONTRACT.md`; `{API_URL}/openapi.json` is the tie-breaker. Previous plan (15:00 gate, done): `docs/superpowers/plans/2026-10-17-person-c-dashboard-1500.md` — its Global Constraints still apply.

## Global Constraints

- Lane: this plan touches `web/` and, in `api/`, only the new `api/routes_employees.py`, `api/test_employees.py`, two model classes appended to `api/models.py`, two functions appended to `api/db.py`, and one `include_router` line in `api/main.py`. Nothing else in `api/`, `engine/` changes.
- Dashboard **manager** is a cookie flag, not the policy `role` fact. The policy fact stays ∈ `employee`, `contractor`, `intern` (`API_CONTRACT.md`); a person who signs up as "manager" gets policy role `employee` and `manager: true` in the cookie. No passcode (user's call deferred; default is open).
- Cookie `pop_user`: JSON `{"employee_id": string, "name": string, "manager": boolean}`, `httpOnly`, `sameSite: "lax"`, `path: "/"`, `maxAge: 2592000` (30 days). Read only through `lib/session.ts`.
- All API calls stay server-side through `lib/api.ts`; still no `NEXT_PUBLIC_*`, still no `"use client"` beyond `app/error.tsx`.
- Route-handler redirects are **303** (`NextResponse.redirect(url, 303)`) so a POST lands on a GET; a page-level `redirect()` (307) stays for GET pages.
- `/check`, `/cases/[id]`, `/approvals` require a signed-in user (`requireUser()` → `redirect("/login")`). `/ledger`, `/rules`, `/eval` stay open.
- Approver recorded on `/approve` is always the cookie's `employee_id`, never a form field.
- Commits: plain messages, no co-author trailer (repo rule). Branch `web-dashboard`, rebased on `main` at `8809002`.

## Review Focus

1. **Tampered or stale cookie** (hand-edited JSON, a user deleted on API restart): `parseUser` returns `null` for anything that is not `{employee_id: string, name: string, manager: boolean}`; a valid cookie whose employee no longer exists gets a 404 from `/check`, which the error page reports — acceptable; the login page is one click away. → Task 2, `lib/session.test.mjs`.
2. **Non-manager opens `/approvals`** (types the URL): sees "Managers only" with a link to sign in as one, not the pending list, and `act/approve` refuses with 403. → Task 4, curl with an employee cookie.
3. **Double Approve** (manager clicks twice, or two managers): the API appends an approval row each time and re-proves; the page simply re-renders the case. `act/approve` on an unknown case returns the API's 404 through the error page. → Task 4, two consecutive curl POSTs both 303.
4. **Authorize on a non-compliant case** (button is hidden, but the POST can be replayed): the API answers 409; the handler must surface that as an error page, not a silent redirect. → Task 3, curl POST on a violation case → 500 page with the 409 text in the server log.
5. **Answer with a value outside the fact's domain** (replayed form): API 422 → same error surface as 4. → Task 3, curl.

---

### Task 1: `POST /employees`, `GET /employees`

**Files:**
- Create: `api/routes_employees.py`, `api/test_employees.py`
- Modify: `api/models.py` (append), `api/db.py` (append two functions), `api/main.py` (router tuple), `web/lib/openapi.d.ts` (regenerate), `web/lib/types.ts` (two re-exports)

**Interfaces:**
- Produces:
  - `POST /employees` body `EmployeeIn {name: str, role: "employee"|"contractor"|"intern", manager_id: str = ""}` → 200 `Employee {employee_id, name, role, manager_id}`, `employee_id = "e_" + secrets.token_hex(4)`; 422 on a role outside the enum (Pydantic `Literal`).
  - `GET /employees` → 200 `EmployeeList {employees: [Employee]}`, seed rows included, ordered by `name`.
  - `db.add_employee(conn, employee_id, name, role, manager_id) -> None`; `db.list_employees(conn) -> list[dict]`.
  - `web/lib/types.ts`: `export type Employee = S["Employee"]; export type EmployeeList = S["EmployeeList"];`

- [ ] **Step 1: Write the failing tests `api/test_employees.py`**

```python
def test_signup_creates_employee_that_check_accepts(client):
    e = client.post("/employees", json={"name": "Priya N", "role": "employee"}).json()
    assert e["employee_id"].startswith("e_") and len(e["employee_id"]) == 10
    assert e["manager_id"] == ""
    assert client.post("/check", json={"text": "Coffee $4", "employee_id": e["employee_id"]}).status_code == 200

def test_signup_rejects_unknown_role(client):
    assert client.post("/employees", json={"name": "X", "role": "cfo"}).status_code == 422

def test_list_employees_includes_seed_and_new(client):
    client.post("/employees", json={"name": "Aaron Z", "role": "intern", "manager_id": "e_manager"})
    names = [e["name"] for e in client.get("/employees").json()["employees"]]
    assert names == sorted(names) and "Dana Ortiz" in names and "Aaron Z" in names
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/pytest -q api/test_employees.py`
Expected: 3 failed — `POST /employees` answers 404 / 405 (route missing).

- [ ] **Step 3: Implement** — `api/models.py`: `class EmployeeIn(_M)`, `class Employee(_M)`, `class EmployeeList(_M)` per the Interfaces block (`role: Literal["employee", "contractor", "intern"]`). `api/db.py`: `add_employee` (`INSERT INTO employees VALUES (?,?,?,?)` + commit), `list_employees` (`SELECT * FROM employees ORDER BY name`, rows as dicts like `_one` does). `api/routes_employees.py`: `router = APIRouter()`, the two routes using `with closing(db.connect()) as conn:` like `routes_cases.py`. `api/main.py`: add `routes_employees` to the import and the `for m in (...)` tuple.

- [ ] **Step 4: Run the tests to verify they pass, then the whole suite**

Run: `.venv/bin/pytest -q api/test_employees.py` → `3 passed`. Then `.venv/bin/pytest -q` → all pass (was 182 passed, 1 skipped).

- [ ] **Step 5: Restart the API and regenerate the dashboard types**

Run from the repo root: `pkill -f "uvicorn api.main:app"; (.venv/bin/uvicorn api.main:app --port 8000 &)` then from `web/`: `pnpm dlx openapi-typescript http://localhost:8000/openapi.json -o lib/openapi.d.ts` and append the two re-exports to `lib/types.ts`.
Expected: `grep -cE '^\s+(Employee|EmployeeList|EmployeeIn): \{' lib/openapi.d.ts` prints `3`.

- [ ] **Step 6: Commit**

```bash
git add api/routes_employees.py api/test_employees.py api/models.py api/db.py api/main.py web/lib
git commit -m "feat(api): POST/GET /employees for dashboard signup"
```

---

### Task 2: Session cookie, login/signup page, action route handler, nav

**Files:**
- Create: `web/lib/session.ts`, `web/lib/session.test.mjs`, `web/app/act/[name]/route.ts`, `web/app/login/page.tsx`
- Modify: `web/app/layout.tsx`, `web/app/check/page.tsx`

**Interfaces:**
- Consumes: `get`, `post` from `lib/api.ts`; `Employee`, `EmployeeList` from `lib/types.ts`.
- Produces:
  - `lib/session.ts`: `export type User = { employee_id: string; name: string; manager: boolean }`; `export const COOKIE = "pop_user"`; `export function parseUser(raw: string | undefined): User | null` (pure: JSON parse in try/catch, then the three fields with the right `typeof`, else `null`); `export async function getUser(): Promise<User | null>` (`(await cookies()).get(COOKIE)?.value` → `parseUser`); `export async function requireUser(): Promise<User>` (`getUser()` or `redirect("/login")`); `export function cookieOptions()` → `{ httpOnly: true, sameSite: "lax" as const, path: "/", maxAge: 2592000 }`.
  - `app/act/[name]/route.ts`: `export async function POST(req: Request, ctx: RouteContext<"/act/[name]">)`. Reads `await req.formData()`. Dispatch on `name`:
    - `signup`: fields `name`, `kind` ∈ `employee|intern|contractor|manager`. `POST /employees {name, role: kind === "manager" ? "employee" : kind, manager_id: kind === "manager" ? "" : "e_manager"}` → set cookie `{employee_id, name, manager: kind === "manager"}` → 303 `/check`.
    - `login`: fields `employee_id`, optional `manager` (checkbox, `"on"`). `GET /employees`, find the row (404-style error if absent) → cookie `{employee_id, name: row.name, manager: manager === "on"}` → 303 `/check`.
    - `logout`: clear the cookie (`maxAge: 0`) → 303 `/login`.
    - `answer`, `approve`, `authorize`: Task 3 and 4 add these; unknown `name` → `new Response("unknown action", { status: 404 })`.
    - A thrown API error propagates (Next returns 500 and logs it) — that is the error surface for Review Focus 4 and 5.
  - `app/login/page.tsx`: two `<form method="post">`s side by side — **Sign up** (`action="/act/signup"`: `name` text required, `kind` select with the four kinds, button `Create account`) and **Sign in as** (`action="/act/login"`: `employee_id` select built from `GET /employees` showing `name (employee_id)`, `manager` checkbox labelled `I approve purchases`, button `Sign in`). If a user is already signed in, the page says so with a `Sign out` form (`action="/act/logout"`).
  - `app/layout.tsx`: when `getUser()` is non-null, the nav shows `{name}` plus a `Manager` chip when `manager`, and a `Sign out` form button; `Approvals` link only when `manager`; when null, a `Sign in` link to `/login`.
  - `app/check/page.tsx`: `const user = await requireUser()`; the employee `<select>` is gone, the handler uses `user.employee_id`; the heading becomes `Can I buy this, {name}?`.

- [ ] **Step 1: Write the failing test `web/lib/session.test.mjs`**

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { parseUser } from "./session.ts";

test("parseUser accepts the exact shape", () => {
  assert.deepEqual(parseUser('{"employee_id":"e_1","name":"Priya","manager":true}'),
                   { employee_id: "e_1", name: "Priya", manager: true });
});
test("parseUser rejects garbage, missing fields and wrong types", () => {
  assert.equal(parseUser(undefined), null);
  assert.equal(parseUser("not json"), null);
  assert.equal(parseUser('{"employee_id":"e_1"}'), null);
  assert.equal(parseUser('{"employee_id":"e_1","name":"P","manager":"yes"}'), null);
});
```

- [ ] **Step 2: Run it to verify it fails**

Run from `web/`: `node --test lib/session.test.mjs`
Expected: FAIL — `Cannot find module './session.ts'`.

- [ ] **Step 3: Implement `lib/session.ts`.** `parseUser` is pure and imports nothing from Next; keep the `next/headers` and `next/navigation` imports for `getUser`/`requireUser` in the same file (Node's type-stripping only evaluates imports that are reached — put `parseUser` first and import `cookies`/`redirect` lazily inside `getUser`/`requireUser` via `await import("next/headers")` so the test never loads Next).

- [ ] **Step 4: Run the test to verify it passes**

Run: `node --test lib/session.test.mjs` → `# pass 2`, `# fail 0`.

- [ ] **Step 5: RED for the pages** — `curl -s -o /dev/null -w '%{http_code}\n' localhost:3000/login` → `404`; `curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' localhost:3000/check` → `200 ` (no redirect yet).

- [ ] **Step 6: Write `app/act/[name]/route.ts`, `app/login/page.tsx`, and modify `layout.tsx` and `check/page.tsx`** per the Interfaces block.

- [ ] **Step 7: Verify**

Run from `web/` (`J` is a scratch cookie jar in the scratchpad dir):
```bash
J=/private/tmp/claude-501/-Users-advaybajpai-lahacks/2d780785-f5a2-427f-9728-4d66ef635561/scratchpad/jar.txt; rm -f $J
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' localhost:3000/check            # 307 .../login
curl -s -o /dev/null -w '%{http_code}\n' localhost:3000/login                              # 200
curl -s -c $J -o /dev/null -w '%{http_code} %{redirect_url}\n' -X POST -d 'name=Priya N&kind=manager' localhost:3000/act/signup   # 303 .../check
grep -c pop_user $J                                                                         # 1
curl -s -b $J localhost:3000/check | grep -oE 'Can I buy this, Priya N\?|name="employee_id"' | sort -u   # only the heading line; no employee select
curl -s -b $J localhost:3000/ledger | grep -oE 'Priya N|Manager|href="/approvals"' | sort -u             # all three
curl -s -c $J -o /dev/null -w '%{http_code} %{redirect_url}\n' -X POST localhost:3000/act/logout          # 303 .../login
curl -s -b $J -o /dev/null -w '%{http_code}\n' localhost:3000/check                          # 307
curl -s -o /dev/null -w '%{http_code}\n' -X POST -d 'x=1' localhost:3000/act/nope             # 404
pnpm build && node --test lib/session.test.mjs lib/format.test.mjs
```
Expected: the values in the comments; build exit 0; `# pass 5`.

- [ ] **Step 8: Commit**

```bash
git add web
git commit -m "feat(web): cookie session, signup/login page, role-aware nav"
```

---

### Task 3: Case page actions — answer, authorize, approval and card rendering, live refresh

**Files:**
- Modify: `web/app/act/[name]/route.ts` (add `answer`, `authorize`), `web/app/cases/[id]/page.tsx`, `web/components/CaseCard.tsx`

**Interfaces:**
- Consumes: `requireUser`, `post`, `Case`, `Authorization`, `usd`.
- Produces:
  - `act/answer`: fields `case_id`, `fact`, `value` (string; `"true"`/`"false"` become booleans, a numeric string for `amount` becomes a number, otherwise the string) → `POST /cases/{case_id}/answer {fact, value}` → 303 `/cases/{case_id}`.
  - `act/authorize`: field `case_id` → `POST /cases/{case_id}/authorize` → 303 `/cases/{case_id}`.
  - `CaseCard` additionally renders: **Approval** line when `c.approval` is non-null — `Approved by {approver} at {at}` (green) or `Rejected by {approver} at {at}` (red); **Authorization** card when `c.authorization` is non-null — `Card authorized · limit {usd(amount_limit)} · {merchant_category} · expires {expires_at}` and `proof {proof_hash}` in mono. `CaseCard` stays free of forms.
  - `/cases/[id]` page: `await requireUser()`; renders `<CaseCard>` then, below it: if `c.questions.length > 0` — the first question's text with one `<form method="post" action="/act/answer">` button per option (`options === null` → `Yes` / `No` with hidden `value` `true`/`false`; else one button per option value); if `c.verdict === "compliant" && !c.authorization` — an `Authorize card` form (`/act/authorize`); if `c.awaiting_approval` — `<meta httpEquiv="refresh" content="5" />` rendered in the page (Next hoists it) and the amber waiting line already in `CaseCard`.

- [ ] **Step 1: RED** — create a real violation case and confirm the page has none of the new markup:

```bash
J=<jar from Task 2 — sign up again if the API restarted>
CID=$(curl -s -X POST localhost:8000/check -H 'content-type: application/json' -d '{"text":"Client dinner with Acme CFO, $48","employee_id":"e_newhire"}' | python3 -c 'import json,sys;print(json.load(sys.stdin)["case_id"])')
curl -s -b $J localhost:3000/cases/$CID | grep -cE 'http-equiv="refresh"|action="/act/authorize"|Approved by'   # 0
curl -s -o /dev/null -w '%{http_code}\n' -X POST -d "case_id=$CID" localhost:3000/act/authorize                 # 404 (unknown action)
```

- [ ] **Step 2: Implement** the two handler branches, the `CaseCard` additions, and the page forms.

- [ ] **Step 3: Verify the waiting → approved → authorized path end to end (the API is real):**

```bash
curl -s -b $J localhost:3000/cases/$CID | grep -c 'http-equiv="refresh"'                                          # 1 (awaiting approval)
curl -s -b $J -o /dev/null -w '%{http_code}\n' -X POST -d "case_id=$CID" localhost:3000/act/authorize              # 500 (API 409 not compliant — Review Focus 4)
grep -c "409" /private/tmp/claude-501/-Users-advaybajpai-lahacks/2d780785-f5a2-427f-9728-4d66ef635561/scratchpad/next-dev.log   # ≥1
curl -s -X POST localhost:8000/cases/$CID/approve -H 'content-type: application/json' -d '{"approver":"e_manager","approved":true}' | python3 -c 'import json,sys;print(json.load(sys.stdin)["verdict"])'   # compliant
curl -s -b $J localhost:3000/cases/$CID | grep -oE 'Approved by e_manager|action="/act/authorize"|http-equiv="refresh"' | sort -u   # first two only
curl -s -b $J -o /dev/null -w '%{http_code} %{redirect_url}\n' -X POST -d "case_id=$CID" localhost:3000/act/authorize   # 303 .../cases/$CID
curl -s -b $J localhost:3000/cases/$CID | grep -oE 'Card authorized|\$48\.00|5812 Eating places|proof [0-9a-f]{64}' | sort -u | wc -l   # 4
curl -s localhost:3000/ledger | grep -c "$CID"                                                                     # ≥1 — the authorized case is in the ledger
```

- [ ] **Step 4: Verify a question button and a bad answer (Review Focus 5):**

```bash
curl -s -b $J -o /dev/null -w '%{http_code}\n' -X POST -d "case_id=$CID&fact=client_present&value=maybe" localhost:3000/act/answer   # 500 (API 422)
QID=$(curl -s -X POST localhost:8000/check -H 'content-type: application/json' -d '{"text":"Dinner, $20","employee_id":"e_newhire"}' | python3 -c 'import json,sys;c=json.load(sys.stdin);print(c["case_id"], c["verdict"], [q["fact"] for q in c["questions"]])')
echo "$QID"   # if verdict is undetermined, the page must show one button per option / Yes-No for questions[0]; POST act/answer with the first option → 303
pnpm build
```
Expected: the 500, the build exit 0; if the engine returns `undetermined` for that text, `curl -s -b $J localhost:3000/cases/<id> | grep -c 'action="/act/answer"'` ≥ 1 and the answer POST → 303.

- [ ] **Step 5: Commit**

```bash
git add web
git commit -m "feat(web): case actions — answer, authorize, approval and card, live refresh"
```

---

### Task 4: Approvals tab for managers

**Files:**
- Modify: `web/app/act/[name]/route.ts` (add `approve`), `web/app/approvals/page.tsx`

**Interfaces:**
- Consumes: `requireUser`, `getUser`, `post`, `get`, `CaseList`.
- Produces:
  - `act/approve`: requires a user with `manager === true` else `new Response("managers only", { status: 403 })`; fields `case_id`, `approved` (`"true"`/`"false"`) → `POST /cases/{case_id}/approve {approver: user.employee_id, approved}` → 303 `/approvals`.
  - `/approvals` page: `const user = await requireUser()`; if `!user.manager` render `Managers only — sign in as a manager` linking to `/login`; else the pending list from Task 6 of the previous plan plus, per case, two forms to `/act/approve` (hidden `case_id`; buttons `Approve` with `approved=true` and `Reject` with `approved=false`) and `<meta httpEquiv="refresh" content="5" />` so a second laptop's new case appears without a click.

- [ ] **Step 1: RED**

```bash
E=<jar>; curl -s -c $E -o /dev/null -X POST -d 'name=Sam New&kind=employee' localhost:3000/act/signup
curl -s -b $E localhost:3000/approvals | grep -c 'Managers only'          # 0
curl -s -b $E -o /dev/null -w '%{http_code}\n' -X POST -d "case_id=x&approved=true" localhost:3000/act/approve   # 404 (unknown action)
```

- [ ] **Step 2: Implement** the handler branch and the page.

- [ ] **Step 3: Verify, two cookies = two laptops**

```bash
M=<manager jar from Task 2>; E=<employee jar>
CID=$(curl -s -X POST localhost:8000/check -H 'content-type: application/json' -d '{"text":"Team dinner with a client, $90","employee_id":"e_newhire"}' | python3 -c 'import json,sys;print(json.load(sys.stdin)["case_id"])')
curl -s -b $E localhost:3000/approvals | grep -c 'Managers only'                                            # 1  (Review Focus 2)
curl -s -b $E -o /dev/null -w '%{http_code}\n' -X POST -d "case_id=$CID&approved=true" localhost:3000/act/approve   # 403
curl -s -b $M localhost:3000/approvals | grep -oE "$CID|http-equiv=\"refresh\"|>Approve<|>Reject<" | sort -u | wc -l   # 4
curl -s -b $M -o /dev/null -w '%{http_code} %{redirect_url}\n' -X POST -d "case_id=$CID&approved=true" localhost:3000/act/approve   # 303 .../approvals
curl -s -b $M -o /dev/null -w '%{http_code}\n' -X POST -d "case_id=$CID&approved=true" localhost:3000/act/approve   # 303 again (Review Focus 3)
curl -s -b $M localhost:3000/approvals | grep -c "$CID"                                                     # 0 — no longer pending
curl -s -b $E localhost:3000/cases/$CID | grep -oE 'Approved by e_[0-9a-f]{8}|compliant|action="/act/authorize"' | sort -u | wc -l   # 3 — the employee's laptop sees it
curl -s -b $M -o /dev/null -w '%{http_code}\n' -X POST -d "case_id=c_00000000&approved=true" localhost:3000/act/approve   # 500 (API 404)
pnpm build
```

- [ ] **Step 4: Commit**

```bash
git add web
git commit -m "feat(web): manager approvals with approve/reject and live refresh"
```

---

### Task 5: UI cleanup

**Files:**
- Create: `web/lib/ui.ts`
- Modify: every page under `web/app/`, `web/components/CaseCard.tsx`, `web/app/layout.tsx`

**Interfaces:**
- Produces `lib/ui.ts` with four exported class strings and nothing else: `muted` (the string every page currently duplicates), `card` (`rounded-lg border border-zinc-200 p-5 dark:border-zinc-800`), `btn` (`rounded border border-zinc-300 px-3 py-1.5 text-sm hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800`), `btnPrimary` (`rounded bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900`). Every page imports these instead of inline duplicates; every page gets one `<h1 className="text-xl font-semibold">` at the top (`Check`, `Case {id}`, `Ledger`, `Rules`, `Evaluation`, `Approvals`, `Sign in`); the nav highlights nothing (no client state) but gets `gap-5` and a thin bottom border — already there. Approve is `btnPrimary`, Reject and Yes/No/option buttons are `btn`. Amount in the facts table renders through `usd` (reviewer minor #4). `web/README.md` is deleted (reviewer minor #7).

- [ ] **Step 1: RED** — `grep -rc 'text-zinc-500 dark:text-zinc-400' app components | grep -v ':0'` lists ≥ 5 files; `test -f README.md && echo present`.

- [ ] **Step 2: Implement.**

- [ ] **Step 3: Verify** — the grep above now lists only `lib/ui.ts`... (run `grep -rl 'text-zinc-500 dark:text-zinc-400' app components lib` → exactly `lib/ui.ts`); `test -f README.md || echo gone`; `pnpm build`; `for p in login check ledger rules eval approvals; do curl -s -o /dev/null -w "$p %{http_code}\n" -b $M localhost:3000/$p; done` → all 200; `curl -s -b $M localhost:3000/cases/$CID | grep -c '\$90\.00'` ≥ 1.

- [ ] **Step 4: Commit**

```bash
git add web
git commit -m "style(web): shared ui classes, page headings, money in facts table"
```

---

## Hand-off

- **Deploy:** unchanged from the previous plan — Vercel root `web`, env `API_URL`. Cookies are per browser, so two laptops are two users against one API; `sameSite: lax` keeps the form POSTs working on the Vercel origin.
- **02:00:** ledger filters and drawer, bank-rule checker, eval chart. Nothing here blocks them; `act/[name]` takes new verbs by adding a case to the switch.
