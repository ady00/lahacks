"""Profile and validate the public QuickBooks participant archive without extracting it."""
import collections
import json
import statistics
import tarfile
from decimal import Decimal
from pathlib import Path

import yaml

OUT = Path('analysis')
OUT.mkdir(exist_ok=True)
def cents(value):
    return int(Decimal(str(value)) * 100)

counts = collections.Counter()
nonempty = collections.Counter()
errors = collections.Counter()
purposes = collections.Counter()
dates = set()
aging = {'ar': collections.Counter(), 'ap': collections.Counter()}
companies = []
index_mismatches = []
schema_hashes = set()

def analyze(cid, data, idx):
    for key, rows in data.items():
        if isinstance(rows, list):
            counts[key] += len(rows)
            nonempty[key] += bool(rows)
            if len(rows) != idx['entity_counts'].get(key, len(rows)):
                index_mismatches.append([cid, key, len(rows), idx['entity_counts'].get(key)])
            ids = [r['id'] for r in rows if 'id' in r]
            errors['duplicate_ids_within_company_entity'] += len(ids) - len(set(ids))
    for name in ('invoices', 'sales_receipts'):
        for row in data[name]:
            errors['document_line_sum'] += cents(row['total_amount']) != sum(cents(x['amount']) for x in row['lines'])
    for row in data['bills']:
        errors['bill_line_sum'] += cents(row['total_amount']) != sum(cents(x['amount']) for x in row['item_lines'] + row['account_lines'])
    for row in data['journal_entries']:
        purposes[row['purpose']] += 1
        errors['unbalanced_journal'] += sum(cents(x['debit_amount'])-cents(x['credit_amount']) for x in row['lines']) != 0
    for payment_name, doc_name in [('customer_payments','invoices'), ('bill_payments','bills')]:
        doc_ids = {r['id'] for r in data[doc_name]}
        for row in data[payment_name]:
            errors['missing_payment_document'] += sum(a['document_id'] not in doc_ids for a in row['applications'])
            errors['payment_application_sum'] += cents(row['amount']) != sum(cents(a['amount']) for a in row['applications']) + cents(row.get('unapplied_amount', 0))
    running = 0
    for row in data['bank_transactions']:
        running += cents(row['amount'])
        errors['bank_running_balance'] += running != cents(row['running_balance_amount'])
        dates.add(row['date'])
    errors['bank_vs_index_cash'] += running != idx['financials_cents']['cash']
    bs = data['balance_sheet']['period_end']
    errors['balance_sheet_equation'] += cents(bs['total_assets']) != cents(bs['total_liabilities']) + cents(bs['total_equity'])
    pnl = data['profit_and_loss']
    errors['profit_vs_index'] += cents(pnl['full_period']['net_profit']) != idx['financials_cents']['profit']
    errors['monthly_profit_sum'] += sum(cents(m['net_profit']) for m in pnl['monthly']) != cents(pnl['full_period']['net_profit'])
    for typ in ('ar','ap'):
        report = data[typ + '_aging']
        aging[typ].update({k:cents(v) for k,v in report['buckets'].items()})
        errors['aging_bucket_sum'] += sum(cents(v) for v in report['buckets'].values()) != cents(report['total_outstanding'])
    ar = data['ar_aging']
    companies.append({**{k:idx[k] for k in ['company_id','display_name','profile','business_status','distressed']},
        'financials_usd':{k:v/100 for k,v in idx['financials_cents'].items()},
        'ar_overdue_usd':sum(cents(v) for k,v in ar['buckets'].items() if k != 'current')/100,
        'period_start':pnl['period_start_date'],'period_end':pnl['period_end_date'],
        'months':len(pnl['monthly']),'full_months':sum(m['full_calendar_month'] for m in pnl['monthly'])})

with tarfile.open('data/hackathon-100-participant.tar.gz') as archive:
    index = json.load(archive.extractfile('hackathon-100/index.json'))
    lookup = {c['company_id']:c for c in index}
    (OUT/'index.json').write_text(json.dumps(index,indent=2),encoding='utf-8')
    (OUT/'DATA_README.md').write_bytes(archive.extractfile('hackathon-100/DATA_README.md').read())
    current, data = None, {}
    files = [m for m in archive.getmembers() if m.isfile()]
    for member in files:
        parts = member.name.split('/')
        if len(parts)<3 or not parts[1].startswith('company-'):
            continue
        cid = parts[1]
        if cid != current:
            if current:
                analyze(current,data,lookup[current])
                if len(companies)%10==0:
                    print(f'Analyzed {len(companies)} companies',flush=True)
            current, data = cid, {}
        if member.name.endswith('SCHEMA.md'):
            content = archive.extractfile(member).read()
            schema_hashes.add(content)
            (OUT/'SCHEMA.md').write_bytes(content)
        elif member.name.endswith('.yaml'):
            data[Path(member.name).stem] = yaml.load(archive.extractfile(member),Loader=yaml.CSafeLoader)
    analyze(current,data,lookup[current])

financials = {}
for field in index[0]['financials_cents']:
    values = [c['financials_cents'][field]/100 for c in index]
    financials[field] = {'min':min(values),'median':statistics.median(values),'max':max(values),'total':round(sum(values),2)}
result = {
    'company_count':len(index),'file_count':len(files),'uncompressed_bytes':sum(m.size for m in files),
    'profiles':dict(collections.Counter(c['profile'] for c in index)),
    'size_tiers':dict(collections.Counter(c['size_tier'] for c in index)),
    'unique_industries':len({c['industry_naics'] for c in index}),
    'distressed_companies':sum(c['distressed'] for c in index),
    'loss_making_companies':sum(c['financials_cents']['profit']<0 for c in index),
    'business_statuses':dict(collections.Counter(c['business_status'] for c in index)),
    'actual_entity_counts':dict(counts),'companies_with_entity':dict(nonempty),
    'financials_usd':financials,'aging_usd':{k:{b:v/100 for b,v in bs.items()} for k,bs in aging.items()},
    'bank_date_range':[min(dates),max(dates)],'report_periods':sorted({(c['period_start'],c['period_end']) for c in companies}),
    'validation_error_counts':dict(errors),'index_count_mismatches':index_mismatches,
    'distinct_schemas':len(schema_hashes),'journal_purposes':dict(purposes),
    'hidden_files':sum('/hidden/' in m.name for m in files),
    'companies':sorted(companies,key=lambda c:c['company_id'])
}
(OUT/'profile.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='companies'},indent=2))
