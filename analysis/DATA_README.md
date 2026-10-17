# Hackathon-100: Synthetic QuickBooks Company Dataset

One hundred synthetic small businesses, each with one year of internally
consistent books in QuickBooks-shaped entities. Built with qb-world-sim for the
"QuickBooks: Reimagining Accounting With System One Models" hackathon.

This is provider-neutral YAML in qb-world-sim's realized-world model (RWM), not
a native QBO export/import package. Field-level schema: `SCHEMA.md` inside
every company directory.

## What you get

```
index.json                     all 100 companies: name, industry, size, headline financials
DATA_README.md                 this file
company-001/ ... company-100/  one directory per company
  rwm-v4/world-<id>/           the company's books (YAML, one file per entity type)
                               (v4 is the schema version; manifest.yaml also
                               records the generator's realize_version)
    company.yaml               profile: name, industry, address, fiscal year
    accounts.yaml              chart of accounts (industry-pruned; see conventions)
    customers.yaml             customers with payment terms and credit limits
    vendors.yaml               vendors (suppliers, landlord, utilities, ...)
    employees.yaml             staff with job titles, wages, hire/release dates
    items.yaml                 products and services sold
    invoices.yaml              invoices with line items and due dates
    sales_receipts.yaml        point-of-sale takings, desk payments, donations
    customer_payments.yaml     payments applied to invoices
    bills.yaml                 vendor bills with due dates
    bill_payments.yaml         payments applied to bills
    journal_entries.yaml       everything else: COGS, wages, interest, depreciation,
                               card-clearing, write-offs, owner draws
    projects.yaml              jobs (project-based companies)
    bank_transactions.yaml     bank-side feed of the checking account, dated by settlement
    estimates.yaml             bids with won/lost status (project-based companies)
    terms.yaml                 the payment terms in use across customers and vendors
    payroll_runs.yaml          per-employee gross pay runs (no withholding modeled)
    reports/
      profit_and_loss.yaml     full period plus monthly series
      balance_sheet.yaml       period end plus quarter-end snapshots
      ar_aging.yaml            receivables aged current/1-30/31-60/61-90/90+
      ap_aging.yaml            payables aged the same way
    manifest.yaml              provenance: dataset id, seed, config, entity counts
    SCHEMA.md                  full field-level schema reference
    hidden/                    simulation ground truth (personas, market context,
                               management decisions) -- see note below
```

Empty entity files are normal and meaningful: a cafe has no invoices (it sells
at the register), a bookkeeping firm has no sales receipts, only project-based
companies have projects and estimates.

## The companies

- Seven business shapes: 22 wholesale distributors, 22 project contractors
  (construction, architecture, film, catering, landscaping, events...), 12
  supply-and-install businesses, 16 recurring-services firms (bookkeeping,
  landlords, advisors), 14 point-of-sale businesses (restaurants, cafes,
  shops), 10 appointment practices (dental, law, salons), 4 nonprofits.
- 71 distinct industries, 3 size tiers (`size_tier` is a scenario label, not a
  validated real-world size class).
- Every company has 365 days of history over the same window, ending early
  October 2026, opening with an owner contribution. These are one-year
  histories, not mature multi-year books: there are no carry-forward balances
  and no basis for year-over-year analysis.
- Some companies are failing: `distressed: true` in index.json marks companies
  that lost money and are insolvent or wound down. It is derived from
  financials; `business_status` (`open`/`operating`/`wound_down`) is the
  operational state, so a distressed company can still read `open`.
- Payment behavior varies per company: most customers pay late, some pay early
  or on time, and a slice of invoices is never paid and written off.
- Profitable for-profit companies accrue an income-tax provision; many owners
  draw profits quarterly (the Owner Distributions equity account). Nonprofits
  accrue no income tax and take no draws.

## Conventions you need to know

- **IDs are company-scoped.** `cust-customer-3` exists in many companies and
  names a different party in each. Scope every lookup by company. Names also
  repeat across companies; they are unique only within one company.
- **Money is decimal strings** (`"1234.56"`), always two places, in a
  `*_amount` field; the simulation level uses integer cents.
- **Bank feed signs**: `amount` already carries its sign with accounting
  convention -- debit increases checking, credit decreases it. The running
  balance is cumulative.
- **Charts differ by industry.** Revenue accounts a business can never post
  to are dropped (a law firm has no Construction Income; a nonprofit has no
  Income Tax or Owner Distributions), and the main revenue account carries an
  industry display name ("Patient Service Income", "Rental Income") -- though
  its subtype and description stay generic. The rest of the chart is a shared
  36-account template, so service firms still carry an unused Inventory Asset
  and job-cost accounts. Account ids are stable across companies.
- **Doc numbers are advisory**; nothing should key on them.
- **The observation date is fixed**: every status (open balances, aging) is as
  of the final simulation day.
- **`hidden/` is simulation context**, not books: customer personas, market
  context, management decisions. The numeric traits on personas are real
  simulation parameters; the prose (temperament, contact preference) is
  synthetic flavor, NOT derived from the recorded behaviour -- do not score
  against it. If a track scores an agent on inferring management or market
  facts, keep the relevant hidden files organizer-only; the directory name
  does not restrict access.

## Guarantees

- **Books balance.** Every company passes two independent checks at
  generation: a full event replay that proves the accounting equation holds
  every day, and a cent-level reconciliation of the realized books against the
  simulation (AR/AP sub-ledgers sampled through the year). An independent
  audit re-verified line arithmetic, payment applications, journal balance,
  bank running balances, payroll sums, and report arithmetic across all 100
  companies with zero errors.
- **Deterministic.** Each company regenerates byte-for-byte from the committed
  manifest (`datasets/hackathon-100/manifest.json` in qb-world-sim) at the
  source commit named below. The dataset id in each manifest.yaml is a content
  hash of the inputs.
  Regenerate with: `python3 tools/hackathon_batch.py run --out runs/my-batch`
  at qb-world-sim commit `687fddf25868b79f1811720471b39e84bdb150b9` (branch feat/hackathon-batch-dataset).
- **Synthetic.** No real customer data anywhere. Names, addresses, and phone
  numbers are generated; all email domains are `.example`. Dollar amounts are
  plausible, not calibrated to any real company.

## What this dataset is good for -- and not

Well supported: financial Q&A, company health summaries, cash-flow dashboards,
collections and AP prioritization, invoice/payment linking, aging analysis,
project profitability, cross-company comparison.

Not sufficient without extension: SKU/basket/menu analytics (POS companies
aggregate to daily takings on one item), payroll or tax calculation (gross-only
payroll, simplified tax provision), messy-books repair or unmatched-bank-feed
reconciliation (the feed matches the books exactly -- inject your own mess),
customer-retention modeling for POS (one walk-in aggregate customer), and
multi-year forecasting (one year of history).

## Modifying the data

Per the hackathon rules, you may modify or extend the data -- delete rows,
change numbers, inject messiness -- but **disclose what you changed and why**
in your submission. If you want more companies or longer histories, the
generator is one command in the qb-world-sim repo:

```sh
python3 tools/hackathon_batch.py run --out runs/my-batch
```

## Known limitations

- Single-line invoices (one item per invoice; multi-item companies spread
  items across invoices).
- No sales tax, credit memos, refunds, classes, or locations.
- Payroll is gross wages only -- no withholding or payroll taxes -- and each
  employee's pay is its own payroll run (real QBO groups a payday into one run).
- Every customer payment settles exactly one invoice (sometimes in
  installments) and every bill payment one bill; no multi-invoice checks,
  overpayments, or credit balances.
- Recurring-service companies sell one service item; service businesses carry
  shallow catalogs generally.
- Landlord companies model fee streams, not owned buildings: no fixed-asset
  property or depreciation on their balance sheets.
- The retail bakery buys finished goods for resale; no manufacturing or recipe
  costing anywhere in the set.

## Known artifacts

Synthetic data has fingerprints. The ones we know about:

- **First-quarter ramp (project companies).** Wholesale, mixed, and service
  companies open with an established base, so revenue is roughly steady.
  Project-based companies start with an empty pipeline, so their first quarter
  runs light and milestone revenue stays lumpy all year. The first and last
  entries of the monthly P&L series are partial calendar months -- check
  `full_calendar_month` and `days_covered` before computing trends.
- **Weekday B2B trading.** Wholesale, mixed and project companies invoice on
  weekdays only. Appointment and recurring-service firms do invoice on
  weekends, and register sales run on each company's open days.
- **AP ages young.** Companies pay vendor bills promptly, so payables rarely
  age past 30 days; receivables carry the aging signal.
- **No standalone-construction owner draws.** Pure construction contractors
  retain all earnings, so a profitable contractor's cash builds up.
- **Clean feeds.** The bank feed follows booked cash exactly; there are no
  unmatched or duplicate feed lines to reconcile.
- **Wholesale price structure.** Wholesale invoice amounts are quantity times
  list price. Prices vary across companies and drift through the year, but
  within one company amounts cluster more than organic QBO data would.
