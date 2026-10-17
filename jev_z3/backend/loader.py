"""Read the participant tarball without extracting files or mutating source data."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile

import yaml

from .models import AccountingLine, Model, PurchaseCase, Settlement, money_cents


class LoadResult(Model):
    purchases: list[PurchaseCase]
    employees: list[dict]
    manifest: dict


def load_records(path: str | Path) -> list[PurchaseCase]:
    with open(path, encoding="utf-8") as stream:
        return [PurchaseCase.model_validate(json.loads(line)) for line in stream if line.strip()]


NEEDED = {"company", "manifest", "bills", "bill_payments", "bank_transactions", "vendors", "employees", "accounts", "items"}


def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _index(rows, name):
    index = {r["id"]: r for r in rows}
    if len(index) != len(rows):
        raise ValueError(f"Duplicate IDs in {name}")
    return index


def normalize_company(company_id: str, data: dict, *, policy_version="demo-2026-10-17-v1"):
    for key in NEEDED:
        if key not in data:
            raise ValueError(f"{company_id}: missing {key}.yaml")
    manifest = data["manifest"]
    if manifest["currency"] != "USD":
        raise ValueError("Only USD is supported")
    as_of = date.fromisoformat(manifest["anchor_date"]) + timedelta(days=manifest["sim"]["days"])
    bills = _index(data["bills"], "bills")
    vendors = _index(data["vendors"], "vendors")
    accounts = _index(data["accounts"], "accounts")
    items = _index(data["items"], "items")
    payments = _index(data["bill_payments"], "bill_payments")
    _index(data["bank_transactions"], "bank_transactions")
    _index(data["employees"], "employees")
    bank_by_source = defaultdict(list)
    for row in data["bank_transactions"]:
        if row["source_document_id"] in payments:
            bank_by_source[row["source_document_id"]].append(row)
    settlements = defaultdict(list)
    for payment in payments.values():
        bank = bank_by_source[payment["id"]]
        if not bank:
            raise ValueError(f"{company_id}: no bank entry for {payment['id']}")
        paid = money_cents(payment["amount"])
        if any(money_cents(b["amount"]) >= 0 for b in bank) or -sum(money_cents(b["amount"]) for b in bank) != paid:
            raise ValueError(f"{company_id}: payment/bank amount mismatch {payment['id']}")
        if any(b["date"] != payment["txn_date"] for b in bank):
            raise ValueError(f"{company_id}: settlement date mismatch {payment['id']}")
        if sum(money_cents(a["amount"]) for a in payment["applications"]) != paid:
            raise ValueError(f"{company_id}: payment allocations do not sum {payment['id']}")
        for application in payment["applications"]:
            bid = application["document_id"]
            if bid not in bills or bills[bid]["vendor_id"] != payment["vendor_id"]:
                raise ValueError(f"{company_id}: missing bill or vendor mismatch {bid}")
            settlements[bid].append(Settlement(payment_id=f"{company_id}:{payment['id']}",
                bank_transaction_ids=[f"{company_id}:{b['id']}" for b in bank],
                settlement_date=payment["txn_date"], allocated_cents=money_cents(application["amount"])))
    purchases = []
    for bid in sorted(settlements):
        bill = bills[bid]
        vendor_id = bill["vendor_id"]
        if vendor_id not in vendors:
            raise ValueError(f"{company_id}: missing vendor {vendor_id}")
        lines = []
        for row in bill.get("account_lines", []):
            aid = row["account_id"]
            if aid not in accounts:
                raise ValueError(f"{company_id}: missing account {aid}")
            lines.append(AccountingLine(account_id=aid, account_name=accounts[aid]["name"], description=row.get("description", ""), amount_cents=money_cents(row["amount"])))
        for row in bill.get("item_lines", []):
            item_id = row["item_id"]
            if item_id not in items:
                raise ValueError(f"{company_id}: missing item {item_id}")
            aid = items[item_id].get("purchase_account_id")
            if aid and aid not in accounts:
                raise ValueError(f"{company_id}: missing item purchase account {aid}")
            lines.append(AccountingLine(account_id=aid, account_name=accounts[aid]["name"] if aid else None,
                item_id=f"{company_id}:{item_id}", original_item_id=item_id, description=row.get("description", ""), amount_cents=money_cents(row["amount"])))
        amount = money_cents(bill["total_amount"])
        if sum(line.amount_cents for line in lines) != amount:
            raise ValueError(f"{company_id}: bill line arithmetic mismatch {bid}")
        if sum(s.allocated_cents for s in settlements[bid]) > amount:
            raise ValueError(f"{company_id}: bill overpaid {bid}")
        links = [f"{company_id}:{bid}"]
        for settlement in settlements[bid]:
            links += [settlement.payment_id, *settlement.bank_transaction_ids]
        purchases.append(PurchaseCase(case_id=f"{company_id}:{bid}", company_id=company_id, policy_version=policy_version,
            origin="original", amount_cents=amount, purchase_date=bill["txn_date"], as_of_date=as_of,
            vendor_id=f"{company_id}:{vendor_id}", vendor_name=vendors[vendor_id]["display_name"],
            description=" | ".join([bill.get("memo", ""), *[line.description for line in lines]]),
            accounting_lines=lines, settlements=sorted(settlements[bid], key=lambda s:(s.settlement_date,s.payment_id)),
            source_documents=list(dict.fromkeys(links)),
            provenance={"amount_cents":"bills.total_amount", "purchase_date":"bills.txn_date", "as_of_date":"manifest.anchor_date + sim.days",
                        "original_vendor_id":vendor_id, "original_bill_id":bid, "account_ids":"Original source IDs; scope by company_id",
                        "employee_id":"unknown: no purchase-to-employee link in source", "facts":"unknown unless supplied by evidence or an extraction adapter"}))
    employees = [{"employee_id":f"{company_id}:{e['id']}", "company_id":company_id, "display_name":e["display_name"],
                  "job_title":e["job_title"], "role":None, "source":"employees.yaml"} for e in data["employees"]]
    excluded_outflows = [row for row in data["bank_transactions"] if money_cents(row["amount"]) < 0 and row["source_document_id"] not in payments]
    return purchases, employees, {"bills":len(bills),"cash_purchase_cases":len(purchases),"unpaid_bills_excluded":len(bills)-len(purchases),
                                  "other_bank_outflows_excluded":len(excluded_outflows),
                                  "other_bank_outflows_cents":-sum(money_cents(row["amount"]) for row in excluded_outflows),
                                  "bill_payments":len(payments),"linked_bank_entries":sum(map(len,bank_by_source.values()))}


def load_archive(path: str | Path, company: str = "company-072", *, progress=None) -> LoadResult:
    path = Path(path)
    purchases, employees, stats = [], [], {}
    current, content, seen = None, {}, set()

    def finish():
        if current is None:
            return
        rows, staff, counts = normalize_company(current, content)
        purchases.extend(rows)
        employees.extend(staff)
        stats[current] = counts
        if progress:
            progress(current, counts)

    # Participant archive groups files by company; only one company's YAML is retained.
    with tarfile.open(path, "r|gz") as archive:
        for member in archive:
            if not member.isfile():
                continue
            parts = PurePosixPath(member.name).parts
            if ".." in parts or member.name.startswith("/"):
                raise ValueError("Unsafe archive member path")
            if len(parts)<3 or not re.fullmatch(r"company-\d{3}", parts[1]):
                continue
            cid = parts[1]
            if company != "all" and cid != company:
                continue
            stem = PurePosixPath(member.name).stem
            if not member.name.endswith(".yaml") or stem not in NEEDED:
                continue
            if cid != current:
                finish()
                if cid in seen:
                    raise ValueError("Company files must be grouped in the participant archive")
                seen.add(cid)
                current, content = cid, {}
            if stem in content:
                raise ValueError(f"Duplicate entity file: {member.name}")
            content[stem] = yaml.load(archive.extractfile(member), Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader))
        finish()
    if not stats:
        raise ValueError(f"No company matched {company}")
    return LoadResult(purchases=purchases, employees=employees, manifest={"schema_version":"1", "source_sha256":file_hash(path),
        "source_filename":path.name, "companies":stats, "company_count":len(stats), "purchase_count":len(purchases),
        "view":"one case per bill with bank-linked settlements; amount is bill total, cash paid is sum of settlements",
        "source_modified":False})
