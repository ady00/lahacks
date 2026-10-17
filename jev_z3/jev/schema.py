"""
TypeSafe Jev question schemas for spend policies, accounting rules, and QuickBooks routing.
These questions define the 'System One' zero-shot decision questions evaluated by Jev.
"""

from typing import Any, Dict

JEV_SPEND_RULE_QUESTIONS: Dict[str, Dict[str, Any]] = {
    "rule_domain": {
        "type": "choice",
        "instructions": "What domain of business spend or financial control does this rule govern?",
        "criteria": {
            "expense_policy": "Rules governing corporate cards, travel, meals, entertainment, or employee reimbursements",
            "quickbooks_routing": "Rules for QuickBooks accounting, chart of accounts assignment, GL classification, or class tagging",
            "procurement_po": "Rules requiring purchase orders, contracts, vendor quotes, or procurement review",
            "tax_compliance": "Rules involving tax withholding, W-9 forms, 1099 tracking, or sales tax",
            "anti_fraud_split": "Rules preventing split transactions, duplicate charges, or invoice structuring to evade approval limits",
        },
    },
    "target_scope": {
        "type": "choice",
        "instructions": "What scope or unit of aggregation does this rule evaluate?",
        "criteria": {
            "single_transaction": "A single purchase, receipt, or transaction",
            "line_item": "An individual line item within an invoice or bill",
            "daily_aggregate": "Total cumulative spend per employee or merchant within a single day",
            "monthly_recurring": "Monthly recurring software licenses, subscriptions, or retainers",
            "per_attendee": "Cost calculated per person or per attendee (e.g., meals per person)",
        },
    },
    "category": {
        "type": "choice",
        "instructions": "Which expense or ledger category does this rule apply to?",
        "criteria": {
            "meals_entertainment": "Dining, food, client entertainment, team dinners, or catering",
            "software_saas": "Software subscriptions, cloud services (AWS/GCP), API credits, or SaaS tools",
            "travel_lodging": "Airlines, hotels, rideshares (Uber/Lyft), rental cars, or flights",
            "office_supplies": "Stationery, office supplies, Amazon office items, breakroom goods",
            "contractor_services": "Freelancers, external agencies, legal fees, or professional consultants",
            "hardware_equipment": "Laptops, monitors, computers, equipment, or physical machinery",
            "general_spend": "General expenses, vendor invoices, or any unspecified company spend",
        },
    },
    "operator": {
        "type": "choice",
        "instructions": "What mathematical threshold condition triggers this rule?",
        "criteria": {
            "greater_than": "Strictly exceeding, higher than, or over a dollar amount",
            "greater_equal": "At least, equal to or above, or starting from a dollar amount",
            "less_than": "Under or strictly below a dollar amount",
            "less_equal": "At most, up to, or less than or equal to a dollar amount",
            "between": "Between a lower and upper dollar range",
            "always": "Applies unconditionally to all transactions in this category or vendor",
        },
    },
    "requires_receipt": {
        "type": "noul",
        "instructions": "Does this rule mandate providing an itemized receipt or proof of purchase?",
    },
    "requires_manager_approval": {
        "type": "noul",
        "instructions": "Does this rule mandate explicit direct manager or supervisor sign-off/approval?",
    },
    "requires_vp_approval": {
        "type": "noul",
        "instructions": "Does this rule mandate executive, VP, Director, or CFO sign-off/approval?",
    },
    "requires_purchase_order": {
        "type": "noul",
        "instructions": "Does this rule mandate an approved Purchase Order (PO) or procurement match?",
    },
    "requires_itemized_attendees": {
        "type": "noul",
        "instructions": "Does this rule mandate listing attendee names, headcount, or guest roster?",
    },
    "requires_w9": {
        "type": "noul",
        "instructions": "Does this rule mandate a signed W-9 tax form or vendor certification on file?",
    },
    "requires_compliance_audit": {
        "type": "noul",
        "instructions": "Does this rule mandate a compliance, legal, or finance audit review?",
    },
    "target_department": {
        "type": "choice",
        "instructions": "Which department or team is designated or required by this rule?",
        "criteria": {
            "engineering": "Engineering, Tech, DevOps, or R&D",
            "sales_marketing": "Sales, Marketing, Growth, or Business Development",
            "finance_legal": "Finance, Accounting, Legal, or Operations",
            "general_admin": "General & Administrative, Facilities, or HR",
            "any": "Not restricted to a specific department or applies company-wide",
        },
    },
    "qb_account": {
        "type": "choice",
        "instructions": "If this rule maps to QuickBooks Chart of Accounts, which account should be assigned?",
        "criteria": {
            "6100_office_supplies": "Account 6100: Office Supplies & Expenses",
            "6200_travel_lodging": "Account 6200: Travel, Airfare & Lodging",
            "6250_meals_entertainment": "Account 6250: Meals & Client Entertainment",
            "6300_software_saas": "Account 6300: Computer & Software Subscriptions",
            "6400_professional_services": "Account 6400: Legal, Professional & Contractor Fees",
            "2000_accounts_payable": "Account 2000: Accounts Payable / Vendor Liability",
            "unassigned": "No specific GL account mapping specified in rule",
        },
    },
    "action": {
        "type": "choice",
        "instructions": "What is the primary enforcement action or consequence of this rule?",
        "criteria": {
            "require_approval": "Halt for human approval or managerial sign-off",
            "auto_approve": "Automatically approve without human intervention",
            "flag_audit": "Flag for post-transaction audit or compliance check",
            "reject": "Strictly block or reject the expense",
            "assign_account": "Automatically categorize and tag in QuickBooks GL",
        },
    },
}

