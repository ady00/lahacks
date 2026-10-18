# QuickBooks Online integration: how it would work for Proof of Purchase

2026-10-17 · research note. Nothing here is built yet.

## What we have today

The ledger is a CSV (`data/transactions.csv`) shaped like a QuickBooks export: vendor, memo, amount, timestamp, `qb_category`, receipt flag. The API loads it, maps `qb_category` to a `coded_account`, runs every policy rule over every row, and shows the audit on the Ledger page. A new purchase goes `POST /check` → case → manager approval → mock card authorization. The bank-rule checker already takes QuickBooks' own bank-rule model (description contains words, amount in a range, assign a category, first match wins).

So the product already speaks QuickBooks' vocabulary. A real integration replaces the CSV with live data and pushes our decisions back.

## Three integration points, in order of value

### 1. Pull the ledger (read): QuickBooks → ledger audit

Replace `data/transactions.csv` with a sync job that reads `Purchase` entities (expenses and card charges) from the company file and writes rows in the same CSV shape, then calls `POST /data/reload`. The API and dashboard do not change.

| QuickBooks field | Our column |
| --- | --- |
| `Purchase.Id` | `txn_id` (prefixed with the realm id so it is unique across companies) |
| `EntityRef` (Vendor) `.name` | `vendor` |
| `PrivateNote` or line `Description` | `memo` |
| `TotalAmt` | `amount` (skip refunds and credits, as the loader already does) |
| `TxnDate` | `timestamp` (date only, so `hour` stays unknown, which is already handled) |
| line `AccountRef.name` (expense account) | `qb_category`, mapped through `extract/mapping.py` |
| `AttachableRef` present | `receipt_attached`, with `Attachable.MetaData.CreateTime` as `receipt_date` |
| custom field or `Class` | `employee_id` (see the gap below) |

- Query: `GET /v3/company/{realmId}/query?query=select * from Purchase where TxnDate > '2026-07-01' startposition 1 maxresults 1000`.
- Keep it fresh with change data capture: `GET /cdc?entities=Purchase,Attachable&changedSince=<last sync>` every few minutes, or subscribe to webhooks (CloudEvents format, HMAC-SHA256 `intuit-signature` header) and reload on each event.
- The 200-row synthetic dataset fits in one query. A real company file is paged, 1,000 rows per page.

**Gap:** QuickBooks has no "which employee made this purchase" field on a `Purchase`. Options: a custom field, a `Class` or `Department` per employee, the card's `PaymentMethodRef` mapped to an employee, or the `Employee` entity when the expense is a reimbursement. Pick one per company at setup; the mapping lives in our employees table.

### 2. Push the decision (write): case → QuickBooks

When a case is authorized (or a ledger row is audited), write the proof back so an accountant sees it in QuickBooks:

- **Category.** Set the `Purchase` line `AccountRef` to the account the rules forced (`coded_account`, e.g. `meals_50` → the company's "Meals, 50%" account). This is the `QuickBooks & Anti-Split` box in the README made real.
- **Audit trail.** Append to `PrivateNote`: `Proof of Purchase: compliant · rules 3.4, IRS-meal · proof 9f86d0…`. The proof hash on the authorization already exists for exactly this.
- **Receipts.** `POST /upload` (multipart) creates an `Attachable` linked to the `Purchase`, which also flips our `receipt_attached` fact on the next sync.
- **New purchases.** After a card authorization settles, create the `Purchase` from the case with the right account and class, so the row arrives in QuickBooks already coded and already proven.

Writes are free on Intuit's metered plans; only reads are counted.

### 3. Import the bank rules (read): QuickBooks → `/bank-rules/check`

QuickBooks bank rules are not exposed by the v3 API as a documented entity, so this stays a CSV or manual paste for now. The checker's input shape already matches theirs, so if the API gains the entity the route does not change.

## Auth and setup

- OAuth 2.0 authorization code flow. Authorize at `https://appcenter.intuit.com/connect/oauth2`, exchange at `https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer`, scope `com.intuit.quickbooks.accounting`. The callback carries `realmId`, the company id that goes in every URL.
- Access tokens last 1 hour; refresh tokens last 100 days and rotate on every refresh, so store the newest one. One row per company: `realm_id, access_token, refresh_token, expires_at`.
- A free developer account gives a sandbox company with sample data at `https://sandbox-quickbooks.api.intuit.com`. Production is `https://quickbooks.api.intuit.com`.
- For a private app used by one company, production keys need Intuit's self-attested security questionnaire but not the full App Store review. App Store listing adds technical, legal and security reviews, repeated yearly.
- Where it lives in this repo: a `qbo/` module on Person A's API (`GET /qbo/connect` → redirect, `GET /qbo/callback` → store tokens, `POST /qbo/sync` → pull purchases, write the CSV, call reload). The dashboard gets one "Connect QuickBooks" button and a "Last synced" line on the Ledger page. The engine and the case shape do not change.

## Limits and cost

| Limit | Value |
| --- | --- |
| Requests per minute per company | 500, at most 10 concurrent |
| Batch endpoint | up to 30 operations per call; throttled at 120 batch calls per minute since 2025-10-31 |
| Query page size | 1,000 rows |
| Change data capture window | 30 days |
| Developer account | free; "Builder" tier allows 500k read calls per month, paid tiers from $300/month |

A hackathon demo and a small company fit inside the free tier by a wide margin.

## Recent changes worth knowing (2025 to 2026)

- Minor versions 1 to 74 were retired on 2025-08-01; send `minorversion=75` or nothing.
- Webhooks moved to the CloudEvents payload. The old format was deprecated 2026-05-15 and shut off 2026-07-31; build against CloudEvents only.
- Intuit's metered App Partner Program (May 2025) counts reads, not writes.
- Intuit Assist now auto-categorizes transactions and flags anomalies inside QuickBooks. It does not check purchases against a written policy before the money is spent, which is this product's lane.

## SDKs

- Python: `intuit-oauth` (Intuit's OAuth client) plus `python-quickbooks` (community, MIT, supports query, CDC, batch, attachments). Both fit the FastAPI side.
- Node: `intuit-oauth` (Intuit) and `node-quickbooks` (community).
- Raw REST with `httpx` is fine and avoids two dependencies; the three calls above are a query, a CDC poll and a sparse update.

## Suggested order

1. Sandbox connect and one `Purchase` query, written into the CSV shape, `POST /data/reload`. The Ledger page then shows real QuickBooks rows with no UI change. Half a day.
2. Sparse update of `AccountRef` and `PrivateNote` on authorize. Half a day.
3. CDC polling on a timer, then webhooks. One day.
4. Receipt upload from the case page. Half a day.

## How long it would take (estimated 2026-10-17, 23:40)

One person, the API already running, nothing built yet. The hackathon gates are 02:00 and 10:30.

| Step | What it is | Time | Risk |
| --- | --- | --- | --- |
| 0 | Intuit developer account, create an app, copy sandbox client id and secret, add `http://localhost:8000/qbo/callback` as a redirect URI | 20 min | Sign-up e-mail verification; nothing else gates sandbox keys |
| 1 | `GET /qbo/connect` (redirect) and `GET /qbo/callback` (code → tokens, store `realm_id, access_token, refresh_token, expires_at` in one SQLite table), refresh when `expires_at` is near | 1.5 h | Refresh tokens rotate on every refresh; store the newest or the connection dies after an hour |
| 2 | `POST /qbo/sync`: query `Purchase` since a date, map to the `transactions.csv` columns above, write the file, call the existing `load_data_dir` | 1.5 h | The sandbox company has no per-employee field, so every row lands on one demo employee unless a `Class` or custom field is mapped first; `TxnDate` is date-only, so `hour` stays unknown (already handled) |
| 3 | Dashboard: "Connect QuickBooks" button and a "Last synced" line on the Ledger page | 30 min | None; one anchor and one line |
| 4 | Write-back on authorize: sparse update of `AccountRef` and `PrivateNote` with the proof hash | 1.5 h | Sparse updates need the current `SyncToken`; read before write |
| 5 | Change data capture poll every few minutes, then webhooks | 1 h, then 1 h | Webhooks need a public URL (the Vultr host) and the CloudEvents payload |

Read-only demo (steps 0 to 3): about 4 hours, so finished by roughly 04:00 if started now, which is after the 02:00 gate and well before 10:30. With write-back (step 4): about 5.5 hours. Polling and webhooks are not worth doing before judging; a manual Sync button tells the same story.

Verdict: doable overnight by one person, with the demo risk concentrated in step 0 (account creation) and the employee mapping in step 2. Everything downstream of the CSV is already built and tested, so the engine, the case shape and the Ledger page do not change.

## Sources

- Intuit OAuth FAQ (token lifetimes): https://developer.intuit.com/app/developer/qbo/docs/develop/authentication-and-authorization/faq
- Minor version retirement: https://developer.intuit.com/app/developer/qbo/docs/learn/explore-the-quickbooks-online-api/minor-versions
- Private app keys without App Store review: https://help.developer.intuit.com/s/article/New-app-assessment-process-FAQ
- Rate limits: https://coefficient.io/quickbooks-api/quickbooks-api-rate-limits
- Upcoming API changes (batch throttle, webhooks): https://blogs.intuit.com/2025/12/01/upcoming-changes-to-apis-and-tools-that-may-impact-your-application/
- App Partner Program pricing: https://blogs.intuit.com/2025/05/15/introducing-the-intuit-app-partner-program/
- python-quickbooks: https://github.com/ej2/python-quickbooks · intuit-oauth (Node): https://github.com/intuit/oauth-jsclient

Rate-limit and pricing figures above come from third-party summaries; confirm them against Intuit's developer portal before relying on them.
