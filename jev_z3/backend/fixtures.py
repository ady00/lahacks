"""Deterministic fixtures with independently authored, explicitly draft labels.

This module deliberately does not import or call the policy evaluator.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path

from .models import Approval, Fact, PurchaseCase, Receipt, digest


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as stream:
        for row in rows:
            if hasattr(row, "model_dump"):
                row = row.model_dump(mode="json")
            stream.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def read_jsonl(path):
    with open(path, encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _templates():
    # name, changes, company verdict, company violations, tax verdict, tax violations
    na, ok, fail, unknown = "not_applicable", "compliant", "violation", "undetermined"
    return [
        ("exact_35", {}, na, [], na, []),
        ("over_35_without_approval", {"amount_cents":3501}, fail, ["COMP-3.4"], na, []),
        ("over_35_approved", {"amount_cents":4800,"pre_approved":True}, ok, [], na, []),
        ("approval_unknown", {"amount_cents":4800,"pre_approved":None}, unknown, [], na, []),
        ("intern_event_ride", {"role":"intern","expense_kind":"rideshare","at_company_event":True}, ok, [], na, []),
        ("intern_personal_ride", {"role":"intern","expense_kind":"rideshare"}, fail, ["COMP-5.2"], na, []),
        ("intern_ride_event_unknown", {"role":"intern","expense_kind":"rideshare","at_company_event":None}, unknown, [], na, []),
        ("employee_ride", {"expense_kind":"rideshare"}, na, [], na, []),
        ("intern_personal_airfare", {"role":"intern","expense_kind":"airfare"}, fail, ["COMP-5.2"], na, []),
        ("intern_event_airfare", {"role":"intern","expense_kind":"airfare","at_company_event":True}, ok, [], na, []),
        ("receipt_day_60", {"age":60,"receipt_required":True}, na, [], na, []),
        ("receipt_day_61_missing", {"age":61,"receipt_required":True}, fail, ["COMP-RECEIPT-60"], na, []),
        ("receipt_timely", {"age":61,"receipt_required":True,"receipt_timely":True,"receipt_attached":True}, ok, [], na, []),
        ("receipt_status_unknown", {"age":75,"receipt_required":True,"receipt_timely":None,"receipt_attached":None}, unknown, [], na, []),
        ("receipt_not_required", {"age":75}, na, [], na, []),
        ("qualified_client_meal", {"expense_kind":"meal","coded_account":"meals_50","client_present":True}, na, [], ok, []),
        ("meal_coded_as_travel", {"expense_kind":"meal","coded_account":"travel","client_present":True}, na, [], fail, ["TAX-MEAL-50"]),
        ("meal_purpose_unknown", {"expense_kind":"meal","coded_account":"office","business_purpose":None}, na, [], unknown, []),
        ("qualified_recreation_meal", {"expense_kind":"meal","coded_account":"meals_100","qualified_employee_recreation":True,"at_company_event":True}, na, [], ok, []),
        ("recreation_wrong_classification", {"expense_kind":"meal","coded_account":"meals_50","qualified_employee_recreation":True}, na, [], fail, ["TAX-MEAL-RECREATION"]),
        ("event_not_enough_evidence", {"expense_kind":"meal","coded_account":"meals_50","qualified_employee_recreation":None,"at_company_event":True}, na, [], unknown, []),
        ("ordinary_entertainment", {"expense_kind":"entertainment","coded_account":"entertainment_0"}, na, [], ok, []),
        ("entertainment_wrong_classification", {"expense_kind":"entertainment","coded_account":"meals_50"}, na, [], fail, ["TAX-ENTERTAINMENT-0"]),
        ("tax_exception_outside_scope", {"expense_kind":"entertainment","other_tax_exception":True}, na, [], na, []),
        ("separate_meal_at_entertainment", {"expense_kind":"meal","coded_account":"meals_50","mixed_entertainment":True,"separately_stated_meal":True}, na, [], ok, []),
        ("unseparated_meal_outside_scope", {"expense_kind":"meal","mixed_entertainment":True}, na, [], na, []),
        ("late_approval", {"amount_cents":4800,"approval_event":"late"}, fail, ["COMP-3.4"], na, []),
        ("same_day_approval_no_time", {"amount_cents":4800,"approval_event":"same_day","pre_approved":None}, unknown, [], na, []),
        ("request_approved_today", {"amount_cents":4800,"approval_event":"requested","stage":"requested"}, ok, [], na, []),
        ("multiple_company_violations", {"amount_cents":6000,"role":"intern","expense_kind":"airfare","receipt_required":True,"age":75}, fail, ["COMP-3.4","COMP-5.2","COMP-RECEIPT-60"], na, []),
        ("known_violation_despite_unknown", {"amount_cents":6000,"role":"intern","expense_kind":"airfare","pre_approved":None}, fail, ["COMP-5.2"], na, []),
        ("company_and_tax_violations", {"amount_cents":4800,"expense_kind":"meal","coded_account":"entertainment_0"}, fail, ["COMP-3.4"], fail, ["TAX-MEAL-50"]),
    ]


def build_fixtures(purchases: list[PurchaseCase], output: str | Path, *, company="company-072") -> dict:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if any(p.origin != "original" for p in purchases) or len({p.case_id for p in purchases}) != len(purchases):
        raise ValueError("Fixture sources must be unique original purchases")
    by_company = defaultdict(list)
    for case in sorted(purchases, key=lambda p:p.case_id):
        by_company[case.company_id].append(case)
    test_company = next((cid for cid in sorted(by_company) if cid != company and len(by_company[cid]) >= 30), None)
    if len(by_company[company]) < 10 or test_company is None:
        raise ValueError("Fixtures need all-company ingestion: 10 demo-company purchases and 30 from a different company")
    original_tune = by_company[company][:10]
    original_test = by_company[test_company][:30]
    cases, labels, splits, additions = [], [], [], []
    for split, rows in [("tuning",original_tune),("test",original_test)]:
        for case in rows:
            cases.append(case)
            labels.append({"case_id":case.case_id,"review_status":"draft","company_verdict":"undetermined","company_rule_ids":[],
                "tax_verdict":"undetermined","tax_rule_ids":[],"rationale":"Source purchases lack approval, employee-event, and tax-qualification evidence. Do not treat missing evidence as false."})
            splits.append({"case_id":case.case_id,"group_id":f"original:{case.company_id}","split":split,"origin":"original"})
    tune_groups = {0,3,4,10,15,18,21,29}
    employee_overlay = [{"employee_id":f"{company}:demo-{role}","company_id":company,"role":role,"display_name":f"Demo {role.title()}","source":"synthetic_overlay"} for role in ["employee","intern","contractor"]]
    phrasing = ["Purchase request: {kind}.","Please review this {kind} expense.","I am recording a {kind} purchase.","Expense description: {kind}.","Can this {kind} purchase be processed?"]
    base = {"role":"employee","expense_kind":"office","coded_account":"office","pre_approved":False,
        "receipt_required":False,"receipt_attached":False,"receipt_timely":False,"client_present":False,"at_company_event":False,
        "business_purpose":True,"employee_present":True,"lavish":False,"qualified_employee_recreation":False,
        "other_tax_exception":False,"mixed_entertainment":False,"separately_stated_meal":False}
    for group, (name, changes, cv, cr, tv, tr) in enumerate(_templates()):
        for variant in range(5):
            values = {**base, **{k:v for k,v in changes.items() if k in base}}
            as_of = date(2026,10,6)
            age = changes.get("age",10)
            purchase_date = as_of-timedelta(days=age)
            cid = f"{company}:synthetic:{group:02d}:{variant}"
            facts = {k:Fact(value=v,source="synthetic_overlay",evidence_id=cid) for k,v in values.items()}
            text = phrasing[variant].format(kind=values["expense_kind"])
            # Actual factual assertions, with no verdict, expected rule ID, or scenario name.
            evidence_text = {
                "client_present": ("A client will attend.", "No client will attend."),
                "at_company_event": ("This is for a company event.", "This is not a company event."),
                "business_purpose": ("The purchase has a business purpose.", "The purchase has no business purpose."),
                "employee_present": ("An employee is present.", "No employee is present."),
                "lavish": ("This expense is lavish.", "This expense is not lavish."),
                "qualified_employee_recreation": ("Recreation primarily benefits non-highly-compensated employees.", "This does not qualify as employee recreation."),
                "other_tax_exception": ("Another tax exception applies and requires specialist review.", "No other tax exception applies."),
                "mixed_entertainment": ("This includes entertainment with a meal.", "This is not a mixed entertainment and meal purchase."),
                "separately_stated_meal": ("The meal is purchased separately or separately stated at its usual selling price.", "The meal is not separately purchased or separately stated."),
            }
            for key, (yes, no) in evidence_text.items():
                if values[key] is not None:
                    text += " " + (yes if values[key] else no)
            approvals, receipts = [], []
            mode = changes.get("approval_event")
            if mode:
                event_date = as_of if mode in {"late","requested"} else purchase_date
                approvals = [Approval(evidence_id=f"{cid}:approval",approver_id=f"{company}:demo-manager",approved=True,
                    approved_at=datetime.combine(event_date,datetime.min.time(),tzinfo=timezone.utc)+timedelta(hours=12))]
            elif values["pre_approved"] is True:
                approvals = [Approval(evidence_id=f"{cid}:approval",approver_id=f"{company}:demo-manager",approved=True,
                    approved_at=datetime.combine(purchase_date-timedelta(days=1),datetime.min.time(),tzinfo=timezone.utc))]
            if values["receipt_timely"] is True:
                receipts = [Receipt(evidence_id=f"{cid}:receipt",submitted_date=purchase_date+timedelta(days=min(age,20)))]
            case = PurchaseCase(case_id=cid,company_id=company,origin="synthetic",description=text,
                amount_cents=changes.get("amount_cents",3500),purchase_date=purchase_date,as_of_date=as_of,
                stage=changes.get("stage","posted"),vendor_id=f"{company}:demo-vendor-{values['expense_kind']}",vendor_name=f"Demo {values['expense_kind'].title()} Vendor",
                employee_id=f"{company}:demo-{values['role']}",facts=facts,approvals=approvals,receipts=receipts,
                provenance={"record":"synthetic_overlay","original_record_modified":"false"})
            cases.append(case)
            labels.append({"case_id":cid,"review_status":"draft","company_verdict":cv,"company_rule_ids":cr,
                "tax_verdict":tv,"tax_rule_ids":tr,"rationale":f"Hand-authored expected outcome for {name.replace('_',' ')}; review against the policy text independently of the engine."})
            splits.append({"case_id":cid,"group_id":f"synthetic:{name}","split":"tuning" if group in tune_groups else "test","origin":"synthetic"})
            additions.append({"case_id":cid,"change":"added_complete_synthetic_purchase","scenario":name,
                "added_fields":sorted(case.model_dump()),"reason":"Exercise explicit PDF policy behavior absent from source accounting data."})
    write_jsonl(output/"cases.jsonl",cases)
    write_jsonl(output/"labels.jsonl",labels)
    write_jsonl(output/"splits.jsonl",splits)
    write_jsonl(output/"employees_overlay.jsonl",employee_overlay)
    manifest = {"schema_version":"1","generator_version":"1","deterministic":True,"company":company,
        "counts":{"original":40,"synthetic":160,"tuning":50,"test":150},"label_review_status":"draft",
        "labels_generated_by_engine":False,"cases_hash":digest([c.model_dump(mode="json") for c in cases]),
        "source_records_hash":digest([c.model_dump(mode="json") for c in purchases]),
        "splits_hash":digest(splits),"source_records_modified":False,"added_employee_roles":employee_overlay,"additions":additions,
        "account_mapping":{"meals_50":"synthetic 50%-limited meal classification","meals_100":"synthetic qualifying employee-recreation meal classification","entertainment_0":"synthetic nondeductible entertainment classification"}}
    write_json(output/"manifest.json",manifest)
    return manifest
