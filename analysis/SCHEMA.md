# Realized World Model schema, version 4

Amounts are two-decimal strings; the dataset currency is in the manifest.
Date-dependent statuses are absent by design and are derived by projecting
the dataset as of a chosen simulation day.

## Books entities

### `company` (CompanyProfile)

The business whose books these are.

| field | type | description |
|---|---|---|
| `id` | str | Stable identifier. |
| `legal_name` | str | Registered name. |
| `trade_name` | str | Name the business trades under. |
| `industry_naics` | str | NAICS industry code. |
| `industry_title` | str | Human-readable NAICS industry title. |
| `email` | str | Primary contact address. |
| `phone` | str | Primary contact number. |
| `website` | str | Public website. |
| `address` | Address | Business address. |
| `fiscal_year_start_month` | int | Month the fiscal year opens, 1 through 12. |
| `opening_sim_day` | int | Simulation day the books open. |
| `opening_date` | str | Calendar date the books open. |
| `sim_actor_id` | str | Simulation actor this profile realizes. |
| `sim_event_ids` | list[str] | Simulation events that produced this entity. |

### `accounts` (Account)

A chart-of-accounts entry required by the postings in this dataset.

| field | type | description |
|---|---|---|
| `id` | str | Stable identifier. |
| `name` | str | Account name as it appears in the chart of accounts. |
| `classification` | str | One of asset, liability, equity, revenue or expense. |
| `account_type` | str | Broad account type, e.g. bank or accounts_receivable. |
| `account_subtype` | str | Narrower type, where the distinction matters. |
| `description` | str | What this account is for in these books. |
| `sim_event_ids` | list[str] | Empty: accounts are structural, not produced by an event. |

### `customers` (Customer)

Someone the business sells to.

| field | type | description |
|---|---|---|
| `id` | str | Stable identifier. |
| `display_name` | str | Name shown on documents and lists. |
| `company_name` | str | Customer's business name. |
| `contact_given_name` | str | Contact's first name. |
| `contact_family_name` | str | Contact's last name. |
| `email` | str | Contact address. |
| `phone` | str | Contact number. |
| `address` | Address | Billing address. |
| `payment_terms` | str | Terms label, e.g. Net 15. |
| `payment_terms_days` | int | Days until payment is due under those terms. |
| `credit_limit_amount` | str | Credit the business extends to this customer. |
| `joined_sim_day` | int | Simulation day the relationship began. |
| `joined_date` | str | Calendar date the relationship began. |
| `ended_sim_day` | int? | Simulation day the relationship ended, if it has. |
| `ended_date` | str? | Calendar date the relationship ended, if it has. |
| `ended_sim_event_id` | str? | Simulation event that ended it, if one did. |
| `notes` | str | Free text carried onto the customer record. |
| `sim_actor_id` | str | Simulation actor this customer realizes. |
| `sim_event_ids` | list[str] | Simulation events that produced this entity. |

### `vendors` (Vendor)

Someone the business buys from.

| field | type | description |
|---|---|---|
| `id` | str | Stable identifier. |
| `display_name` | str | Name shown on documents and lists. |
| `company_name` | str | Vendor's business name. |
| `contact_given_name` | str | Contact's first name. |
| `contact_family_name` | str | Contact's last name. |
| `email` | str | Contact address. |
| `phone` | str | Contact number. |
| `address` | Address | Remittance address. |
| `payment_terms` | str | Terms label, e.g. Net 7. |
| `payment_terms_days` | int | Days until payment is due under those terms. |
| `supply_role` | str | What the vendor supplies: product for goods resold, subcontract for trade labor, premises for rent, utility, insurance, lender for interest, government for permits and tax, or operating for other overhead services. |
| `joined_sim_day` | int | Simulation day the business first dealt with this vendor. |
| `joined_date` | str | Calendar date the business first dealt with this vendor. |
| `sim_actor_id` | str | Simulation actor this vendor realizes. |
| `sim_event_ids` | list[str] | Simulation events that produced this entity. |

### `employees` (Employee)

Someone the business pays wages to.

| field | type | description |
|---|---|---|
| `id` | str | Stable identifier. |
| `display_name` | str | Name shown on lists. |
| `given_name` | str | First name. |
| `family_name` | str | Last name. |
| `email` | str | Work address. |
| `phone` | str | Contact number. |
| `job_title` | str | Role in the business. |
| `hired_sim_day` | int | Simulation day employment began. |
| `hired_date` | str | Calendar date employment began. |
| `released_sim_day` | int? | Simulation day employment ended, if it has. |
| `released_date` | str? | Calendar date employment ended, if it has. |
| `released_sim_event_id` | str? | Simulation event that ended it, if one did. |
| `weekly_wage_amount` | str | Wage earned per week. |
| `sim_actor_id` | str | Simulation actor this employee realizes. |
| `sim_event_ids` | list[str] | Simulation events that produced this entity. |

### `items` (Item)

Something the business buys and resells.

| field | type | description |
|---|---|---|
| `id` | str | Stable identifier. |
| `name` | str | Item name. |
| `sku` | str | Stock-keeping unit code. |
| `description` | str | Description used on sales documents. |
| `item_type` | str | non_inventory for goods, service for work sold by the job. Goods are never inventory-tracked: cost is recognised by explicit journal entries rather than by provider inventory tracking. |
| `unit_price_amount` | str | Price charged per unit. |
| `unit_cost_amount` | str | Cost paid per unit. |
| `income_account_id` | str | Account credited when a unit is sold. |
| `purchase_account_id` | str | Account debited when a unit is bought. This is the inventory asset account, so purchases capitalise instead of expensing immediately. |
| `sim_product_id` | str? | Simulation product this item realizes, where it came from one. Service items describing project work do not. |
| `sim_event_ids` | list[str] | Simulation events that produced this entity. |

### `projects` (Project)

A job the business contracted to carry out for one client.

| field | type | description |
|---|---|---|
| `id` | str | Stable identifier. |
| `name` | str | Name the job is known by. |
| `customer_id` | str | Client the work is for. |
| `customer_name` | str | Client name, carried alongside the id. |
| `project_kind` | str | What sort of job it is, as the simulation classified it. |
| `contract_amount` | str | Agreed consideration with every change order the history approves; a projection gives the figure as of its day. |
| `original_contract_amount` | str | Agreed consideration before any change order. |
| `change_orders` | list[ChangeOrder] | Approved changes to the contract, in order. |
| `started_sim_day` | int | Simulation day the contract was signed. |
| `started_date` | str | Calendar date the contract was signed. |
| `planned_finish_sim_day` | int | Simulation day the work was planned to finish. |
| `planned_finish_date` | str | Calendar date the work was planned to finish. |
| `reschedules` | list[Reschedule] | Agreed delays to the start, in order. |
| `completed_sim_day` | int? | Simulation day the job completed, if it has. |
| `completed_date` | str? | Calendar date the job completed, if it has. |
| `status` | str | Where the job stands at the end of the history; a projection gives the status as of its day. |
| `status_history` | list[StatusChange] | Every status the job entered, in order. |
| `provenance_note` | str | Tag linking this job back to the simulation. |
| `sim_project_id` | str | Simulation project realized here. |
| `sim_event_ids` | list[str] | Simulation events that produced this entity. |

### `invoices` (Invoice)

A sale delivered on credit.

| field | type | description |
|---|---|---|
| `id` | str | Stable identifier. |
| `doc_number` | str | Advisory document number. Providers renumber from their own sequence, so nothing downstream may key on this. |
| `customer_id` | str | Customer billed. |
| `customer_name` | str | Customer name, carried alongside the id. |
| `txn_sim_day` | int | Simulation day of delivery, when the sale was earned. |
| `txn_date` | str | Calendar date of delivery. |
| `due_sim_day` | int | Simulation day payment falls due. |
| `due_date` | str | Calendar date payment falls due. |
| `lines` | list[DocumentLine] | What was sold. |
| `total_amount` | str | Document total; the sum of its lines. |
| `income_account_id` | str | Revenue account this sale is earned into. |
| `project_id` | str? | Project this sale belongs to, where the work is job-costed. |
| `deposit_applied_amount` | str | Part of the total settled by drawing down a deposit already held, rather than becoming receivable. |
| `retainage_amount` | str | Part of the total earned but withheld by the client until the project completes; receivable, but not yet due. |
| `deposit_account_id` | str? | Liability the applied deposit is drawn from, when one is applied. |
| `retainage_account_id` | str? | Asset the withheld retainage is held in, when any is withheld. |
| `memo` | str | Message shown to the customer. |
| `provenance_note` | str | Private tag linking this document back to the simulation. |
| `sim_order_id` | str? | Simulation order fulfilled, where the sale came from one. |
| `sim_obligation_id` | str | Simulation receivable created by that fulfilment. |
| `sim_event_ids` | list[str] | Simulation events that produced this entity. |

### `sales_receipts` (SalesReceipt)

A sale collected at the point of sale, with no receivable created.

| field | type | description |
|---|---|---|
| `id` | str | Stable identifier. |
| `doc_number` | str | Advisory document number; providers renumber it. |
| `customer_id` | str | Customer sold to; the walk-in aggregate for register sales. |
| `customer_name` | str | Customer name, carried alongside the id. |
| `txn_sim_day` | int | Simulation day of the sale. |
| `txn_date` | str | Calendar date of the sale. |
| `lines` | list[DocumentLine] | What was sold. |
| `total_amount` | str | Total collected at the register. |
| `income_account_id` | str | Income account the sale posts to. |
| `deposit_account_id` | str | Where the money landed: checking for cash takings, undeposited funds for card takings awaiting processor settlement. |
| `memo` | str | Note on the receipt. |
| `provenance_note` | str | Private tag linking this record back to the simulation. |
| `sim_event_ids` | list[str] | Simulation events that produced this entity. |

### `customer_payments` (CustomerPayment)

Money received from a customer and applied to their invoices.

| field | type | description |
|---|---|---|
| `id` | str | Stable identifier. |
| `customer_id` | str | Customer who paid. |
| `customer_name` | str | Customer name, carried alongside the id. |
| `txn_sim_day` | int | Simulation day the funds settled. |
| `txn_date` | str | Calendar date the funds settled. |
| `amount` | str | Total received. |
| `applications` | list[PaymentApplication] | Invoices this payment settles. |
| `unapplied_amount` | str | Portion received but not yet applied to an invoice. |
| `settles` | str | What on the invoice the payment settles: its receivable, or the retainage held back from it. |
| `source_account_id` | str | Asset the collection clears. Ordinary collections clear the receivable; a retention release clears retainage held back earlier. |
| `deposit_account_id` | str | Account the funds landed in. |
| `project_id` | str? | Project the collection belongs to, where the invoice it settles is job-costed. A provider that bills jobs as their own customers needs the payment to name the same one. |
| `memo` | str | Note on the receipt. |
| `provenance_note` | str | Private tag linking this record back to the simulation. |
| `sim_payment_id` | str | Simulation payment this realizes. |
| `sim_obligation_id` | str | Simulation receivable settled. |
| `sim_event_ids` | list[str] | Simulation events that produced this entity. |

### `bills` (Bill)

A purchase received on credit, for goods or for overhead.

| field | type | description |
|---|---|---|
| `id` | str | Stable identifier. |
| `doc_number` | str | Advisory document number; providers renumber it. |
| `vendor_id` | str | Vendor billing the business. |
| `vendor_name` | str | Vendor name, carried alongside the id. |
| `expense_kind` | str | product for goods delivered into stock, operating for overhead. |
| `txn_sim_day` | int | Simulation day the liability arose. |
| `txn_date` | str | Calendar date the liability arose. |
| `due_sim_day` | int | Simulation day payment falls due. |
| `due_date` | str | Calendar date payment falls due. |
| `item_lines` | list[DocumentLine] | Goods purchased, for a product bill. |
| `account_lines` | list[AccountLine] | Direct account charges, for an overhead bill. |
| `total_amount` | str | Document total; the sum of all its lines. |
| `project_id` | str? | Project this cost belongs to, where it is job-costed. |
| `cost_category` | str | What the simulator called this cost. The account groups costs the way a QuickBooks chart does; this keeps the distinction the simulator drew. |
| `memo` | str | Note on the bill. |
| `provenance_note` | str | Private tag linking this document back to the simulation. |
| `sim_obligation_id` | str | Simulation payable created. |
| `sim_order_id` | str? | Simulation purchase order, for a product bill. |
| `sim_event_ids` | list[str] | Simulation events that produced this entity. |

### `bill_payments` (BillPayment)

Money paid to a vendor against their bills.

| field | type | description |
|---|---|---|
| `id` | str | Stable identifier. |
| `vendor_id` | str | Vendor paid. |
| `vendor_name` | str | Vendor name, carried alongside the id. |
| `txn_sim_day` | int | Simulation day the funds settled. |
| `txn_date` | str | Calendar date the funds settled. |
| `amount` | str | Total paid. |
| `applications` | list[PaymentApplication] | Bills this payment settles. |
| `payment_account_id` | str | Account the funds left. |
| `memo` | str | Note on the payment. |
| `provenance_note` | str | Private tag linking this record back to the simulation. |
| `sim_payment_id` | str | Simulation payment this realizes. |
| `sim_obligation_id` | str | Simulation payable settled. |
| `sim_event_ids` | list[str] | Simulation events that produced this entity. |

### `journal_entries` (JournalEntry)

A balanced posting for something no commercial document covers.

| field | type | description |
|---|---|---|
| `id` | str | Stable identifier. |
| `doc_number` | str | Advisory document number; providers renumber it. |
| `purpose` | str | Why the entry exists; one of the PURPOSES values: opening_equity, owner_distribution, cost_of_goods, wage_accrual, wage_payment, interest_accrual, depreciation, bad_debt, inventory_disposal, financing_draw, financing_repayment, wip_capitalization, wip_release, deposit_receipt, deposit_refund, client_default or project_wind_down. |
| `txn_sim_day` | int | Simulation day of the posting. |
| `txn_date` | str | Calendar date of the posting. |
| `lines` | list[JournalLine] | The postings, which must balance. |
| `project_id` | str? | Project the entry belongs to, where it moves cost or client money for one job. |
| `memo` | str | Why the entry exists. |
| `provenance_note` | str | Private tag linking this entry back to the simulation. |
| `sim_obligation_id` | str? | Simulation obligation involved, if any. |
| `sim_payment_id` | str? | Simulation payment involved, if any. |
| `sim_event_ids` | list[str] | Simulation events that produced this entity. |

## Derived entities

Computed from the books: a provider derives its own bank feed,
estimates surface, terms list and payroll runs, so these are read
alongside the books but never seeded into one.

### `bank_transactions` (BankTransaction)

One line of the operating account's statement.

| field | type | description |
|---|---|---|
| `id` | str | Stable identifier. |
| `sim_day` | int | Simulation day the cash moved. |
| `date` | str | Calendar date the cash moved. |
| `amount` | str | Signed amount: positive for money in, negative for money out. |
| `direction` | str | debit for money into the account, credit for money out of it. |
| `running_balance_amount` | str | Account balance after this transaction cleared. |
| `source_document_id` | str | Invoice, bill, payment or journal entry that moved the cash. |
| `memo` | str | What the movement was for. |
| `kind` | str | The kind of document behind it, e.g. customer_payment or wage_payment. |
| `sim_event_ids` | list[str] | Simulation events that produced this entity. |

### `estimates` (Estimate)

A quote put to a prospective client, won or lost.

| field | type | description |
|---|---|---|
| `id` | str | Stable identifier. |
| `customer_id` | str? | Client the bid was for, where a won bid became a job for one. |
| `customer_name` | str? | Client name, carried alongside the id, when there is one. |
| `sim_day` | int | Simulation day the bid was submitted. |
| `date` | str | Calendar date the bid was submitted. |
| `amount` | str | Price quoted. |
| `status` | str | won, lost or pending. |
| `project_id` | str? | Project a won bid became, where it did. |
| `invoice_id` | str? | First milestone invoice billed against that project, if derivable. |
| `project_kind` | str | What sort of job was quoted, as the simulation classified it. |
| `provenance_note` | str | Private tag linking this record back to the simulation. |
| `sim_event_ids` | list[str] | Simulation events that produced this entity. |

### `terms` (Terms)

A named set of payment terms the business offers or is given.

| field | type | description |
|---|---|---|
| `id` | str | Stable identifier. |
| `name` | str | Terms label, e.g. Net 15 or Due on receipt. |
| `days` | int | Days until payment is due under these terms. |
| `sim_event_ids` | list[str] | Empty: terms are derived from counterparties, not an event. |

### `payroll_runs` (PayrollRun)

One payroll run: wages paid out on a day, split across the staff paid.

| field | type | description |
|---|---|---|
| `id` | str | Stable identifier. |
| `sim_day` | int | Simulation day the wages were paid. |
| `date` | str | Calendar date the wages were paid. |
| `total_amount` | str | Total paid; the sum of the lines and of the journal entry behind it. |
| `gross_only` | bool | Always true: no withholding or employer taxes are modeled. |
| `lines` | list[PayrollLine] | Per-employee gross pay making up the run. |
| `source_journal_entry_id` | str | Journal entry whose wage payment this run represents. |
| `sim_event_ids` | list[str] | Simulation events that produced this entity. |

## Hidden entities

Context the simulation produced that no accounting provider sees.

### `personas` (Persona)

Character behind a counterparty. Never shown to an accounting provider.

| field | type | description |
|---|---|---|
| `id` | str | Stable identifier. |
| `subject_kind` | str | One of customer, vendor or employee. |
| `subject_id` | str | The realized entity this persona belongs to. |
| `display_name` | str | Name of the person. |
| `role_title` | str | Their role at the counterparty. |
| `temperament` | str | Commercial disposition, as synthetic flavor text; it does not drive and is not derived from the recorded payment behaviour. The traits carry the parameters that do. |
| `contact_preference` | str | How they prefer to be contacted; synthetic flavor. |
| `narrative` | str | Short prose description. For an employee it states only simulated parameters (shipping capacity, role); for others it carries the synthetic temperament. |
| `traits` | list[Trait] | Simulated parameters behind the behaviour. |
| `sim_actor_id` | str | Simulation actor described. |
| `sim_event_ids` | list[str] | Simulation events that produced this entity. |

### `market_context` (MarketContext)

Trading conditions observed on one day.

| field | type | description |
|---|---|---|
| `id` | str | Stable identifier. |
| `sim_day` | int | Simulation day observed. |
| `date` | str | Calendar date observed. |
| `market_demand_percent` | int | Demand level relative to baseline, as a percentage. |
| `observed_demand_units` | int | Units of demand seen in the preceding period. |
| `service_level_percent` | int | Share of demand served on time, as a percentage. |
| `note` | str | What this observation meant for the business. |
| `sim_event_ids` | list[str] | Simulation events that produced this entity. |

### `management_decisions` (ManagementDecision)

A policy choice the business made, with the reasoning behind it.

| field | type | description |
|---|---|---|
| `id` | str | Stable identifier. |
| `sim_day` | int | Simulation day the decision was taken. |
| `date` | str | Calendar date the decision was taken. |
| `decision_kind` | str | What was decided, e.g. stock_policy or staffing. |
| `summary` | str | The decision in one sentence. |
| `observations` | list[Trait] | Figures the decision rested on. |
| `sim_event_ids` | list[str] | Simulation events that produced this entity. |
