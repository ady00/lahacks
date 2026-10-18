from copy import deepcopy
from datetime import date, datetime, timezone
import io
import json
import tarfile

import httpx
import pytest
import yaml

from jev_z3.backend.evaluation import (GeminiJudge, Judgment, Prediction, model_input, run_benchmark,
    summarize, validate_dataset, SEMANTIC_FACTS)
from jev_z3.backend.fixtures import build_fixtures, read_jsonl, write_jsonl
from jev_z3.backend.loader import load_archive, normalize_company
from jev_z3.backend.models import Approval, Fact, PurchaseCase, Receipt, money_cents
from jev_z3.backend.policy import PolicyEvaluator, load_policy_pack
from jev_z3.backend.service import BackendService


def case(**changes):
    values = dict(case_id="company-072:test",company_id="company-072",origin="synthetic",description="Office purchase.",
                  amount_cents=3500,purchase_date="2026-10-01",as_of_date="2026-10-06",
                  facts={key:Fact(value=value,source="test_evidence") for key,value in {
                      "role":"employee","expense_kind":"office","receipt_required":False,"pre_approved":False}.items()})
    values.update(changes)
    return PurchaseCase(**values)


def changed(base, **facts):
    return PurchaseCase.model_validate({**base.model_dump(),"facts":{**base.facts,
        **{k:Fact(value=v,source="test_evidence") for k,v in facts.items()}}})


@pytest.fixture(scope="module")
def evaluator():
    return PolicyEvaluator()


def raw_company():
    return {"company":{},"manifest":{"currency":"USD","anchor_date":"2026-01-01","sim":{"days":100}},
        "vendors":[{"id":"v1","display_name":"Vendor"}], "employees":[{"id":"e1","display_name":"Person","job_title":"Intern"}],
        "accounts":[{"id":"a1","name":"Office"}],"items":[],
        "bills":[{"id":"b1","vendor_id":"v1","total_amount":"35.01","txn_date":"2026-01-02",
                  "account_lines":[{"account_id":"a1","amount":"35.01","description":"Supplies"}]}],
        "bill_payments":[{"id":"p1","vendor_id":"v1","amount":"10.01","txn_date":"2026-01-03","applications":[{"document_id":"b1","amount":"10.01"}]},
                         {"id":"p2","vendor_id":"v1","amount":"25.00","txn_date":"2026-01-04","applications":[{"document_id":"b1","amount":"25.00"}]}],
        "bank_transactions":[{"id":"bank1","source_document_id":"p1","amount":"-10.01","date":"2026-01-03"},
                             {"id":"bank2","source_document_id":"p2","amount":"-25.00","date":"2026-01-04"}]}


def test_ingestion_installments_scoping_exact_money_and_unknowns():
    a, staff, counts = normalize_company("company-001",raw_company())
    b, _, _ = normalize_company("company-002",raw_company())
    assert len(a) == len(b) == 1
    assert a[0].case_id != b[0].case_id
    assert a[0].amount_cents == 3501
    assert [s.allocated_cents for s in a[0].settlements] == [1001,2500]
    assert a[0].purchase_date == date(2026,1,2)
    assert a[0].settlements[0].settlement_date == date(2026,1,3)
    assert len(a[0].source_documents) == 5
    assert a[0].accounting_lines[0].account_id == "a1"
    assert not a[0].facts and not a[0].receipts and not a[0].approvals
    assert a[0].employee_id is None and a[0].purchase_at is None and staff[0]["role"] is None
    assert counts["linked_bank_entries"] == 2
    assert money_cents("0.29") == 29
    for value in ("0.001","NaN","Infinity"):
        with pytest.raises(ValueError):
            money_cents(value)


def test_multi_bill_allocations():
    raw = raw_company()
    raw["bills"].append({**deepcopy(raw["bills"][0]),"id":"b2"})
    raw["bill_payments"][1]["amount"] = "60.01"
    raw["bill_payments"][1]["applications"].append({"document_id":"b2","amount":"35.01"})
    raw["bank_transactions"][1]["amount"] = "-60.01"
    purchases, _, _ = normalize_company("company-001", raw)
    assert len(purchases) == 2
    assert sum(sum(s.allocated_cents for s in c.settlements) for c in purchases) == 7002


@pytest.mark.parametrize("mutation",["duplicate","missing_bill","bank_mismatch","line_mismatch"])
def test_ingestion_rejects_corrupt_joins(mutation):
    raw = raw_company()
    if mutation=="duplicate": raw["bills"].append(deepcopy(raw["bills"][0]))
    if mutation=="missing_bill": raw["bill_payments"][0]["applications"][0]["document_id"]="missing"
    if mutation=="bank_mismatch": raw["bank_transactions"][0]["amount"]="-9.99"
    if mutation=="line_mismatch": raw["bills"][0]["account_lines"][0]["amount"]="35.00"
    with pytest.raises(ValueError): normalize_company("company-001",raw)


def test_safe_archive_read(tmp_path):
    archive = tmp_path/"test.tar.gz"
    with tarfile.open(archive,"w:gz") as tar:
        for cid in ("company-001","company-002"):
            for key,value in raw_company().items():
                blob = yaml.safe_dump(value).encode()
                member = tarfile.TarInfo(f"participant/{cid}/{key}.yaml")
                member.size = len(blob)
                tar.addfile(member,io.BytesIO(blob))
    loaded = load_archive(archive,"all")
    assert loaded.manifest["company_count"] == 2
    assert len(loaded.purchases) == 2
    with tarfile.open(archive,"w:gz") as tar:
        blob = b"!!python/object/apply:os.system ['echo unsafe']"
        member = tarfile.TarInfo("participant/company-001/company.yaml")
        member.size = len(blob)
        tar.addfile(member,io.BytesIO(blob))
    with pytest.raises(yaml.constructor.ConstructorError): load_archive(archive,"all")


@pytest.mark.parametrize("cents,approved,expected",[(3500,False,"not_applicable"),(3501,False,"violation"),(3501,True,"compliant"),(3501,None,"undetermined")])
def test_amount_boundary(evaluator,cents,approved,expected):
    result = evaluator.evaluate(changed(case(amount_cents=cents),pre_approved=approved),suggestions=False)
    assert result.status == "ok"
    assert result.company.verdict == expected


@pytest.mark.parametrize("age,timely,expected",[(60,False,"not_applicable"),(61,False,"violation"),(61,True,"compliant"),(61,None,"undetermined")])
def test_company_receipt_deadline(evaluator,age,timely,expected):
    from datetime import timedelta
    c = changed(case(purchase_date=date(2026,10,6)-timedelta(days=age)),receipt_required=True,receipt_timely=timely)
    assert evaluator.evaluate(c,suggestions=False).company.verdict == expected


@pytest.mark.parametrize("kind,event,expected",[("rideshare",False,"violation"),("airfare",False,"violation"),("rideshare",True,"compliant"),("airfare",None,"undetermined"),("office",False,"not_applicable")])
def test_intern_event_rules(evaluator,kind,event,expected):
    c = changed(case(),role="intern",expense_kind=kind,at_company_event=event)
    assert evaluator.evaluate(c,suggestions=False).company.verdict == expected


def test_approval_timing_and_receipt_evidence(evaluator):
    c = case(amount_cents=4800)
    def approve(at):
        return c.model_copy(update={"approvals":[Approval(evidence_id="a",approver_id="manager",approved=True,approved_at=at)]})
    assert evaluator.evaluate(approve("2026-09-30T12:00:00Z"),suggestions=False).company.verdict == "compliant"
    assert evaluator.evaluate(approve("2026-10-01T12:00:00Z"),suggestions=False).company.verdict == "undetermined"
    assert evaluator.evaluate(approve("2026-10-02T12:00:00Z"),suggestions=False).company.verdict == "violation"
    exact = approve("2026-10-01T12:00:00Z").model_copy(update={"purchase_at":datetime(2026,10,1,13,tzinfo=timezone.utc)})
    assert evaluator.evaluate(exact,suggestions=False).company.verdict == "compliant"
    late = changed(case(purchase_date="2026-08-01"),receipt_required=True).model_copy(update={"receipts":[Receipt(evidence_id="r",submitted_date="2026-10-01")]})
    assert evaluator.evaluate(late,suggestions=False).company.verdict == "violation"


def test_request_answer_approve_cache(evaluator):
    service = BackendService(evaluator)
    original = changed(case(amount_cents=4800,stage="requested"),role="intern",expense_kind="airfare",at_company_event=None,pre_approved=None)
    first = service.check(original)
    assert first.company.verdict == "undetermined"
    assert {q["fact"] for q in first.questions} >= {"at_company_event","pre_approved"}
    assert original.approvals == []
    answered, second = service.answer(original,{"at_company_event":Fact(value=True,source="confirmed_answer")})
    assert second.company.verdict == "undetermined"
    approved, third = service.approve(answered,Approval(evidence_id="manager-approval",approver_id="manager",approved=True,approved_at="2026-10-06T09:00:00Z"))
    assert third.company.verdict == "compliant"
    assert len({first.facts_hash,second.facts_hash,third.facts_hash}) == 3
    assert len(service._cache) == 3
    third.company.verdict = "violation"
    assert service.check(approved).company.verdict == "compliant"
    with pytest.raises(ValueError): service.answer(original,{"pre_approved":Fact(value=True,source="user")})
    modified = load_policy_pack()
    modified["version"] = "new-policy"
    service.evaluator = PolicyEvaluator(modified)
    assert service.check(approved).status == "unsupported"


def test_policy_errors_and_conflicts():
    unknown = {"version":"demo-2026-10-17-v1","rules":[{"id":"bad","layer":"company","when":True,"require":{"magic":[]}}]}
    result = PolicyEvaluator(unknown).evaluate(case())
    assert result.status == "unsupported" and result.company.verdict is None
    conflict = {"version":"demo-2026-10-17-v1","rules":[
        {"id":str(i),"layer":"tax","when":True,"require":{"eq":[{"fact":"coded_account"},value]}}
        for i,value in enumerate(("meals_50","meals_100"))]}
    result = PolicyEvaluator(conflict).evaluate(case())
    assert result.status == "conflicting_policy" and result.tax.verdict is None
    evaluator = PolicyEvaluator()
    evaluator.possible = lambda _: (_ for _ in ()).throw(RuntimeError("timeout"))
    assert evaluator.evaluate(case()).status == "error"


def test_three_way_policy_conflict():
    options = [("office","travel"),("office","other"),("travel","other")]
    pack = {"version":"demo-2026-10-17-v1","rules":[
        {"id":str(i),"layer":"tax","when":True,
         "require":{"or":[{"eq":[{"fact":"coded_account"},value]} for value in values]}}
        for i,values in enumerate(options)]}
    assert PolicyEvaluator(pack).evaluate(case()).status == "conflicting_policy"


def test_tax_qualification_unknown_requires_review(evaluator):
    c = changed(case(),expense_kind="meal",coded_account="meals_50",business_purpose=None,
                employee_present=True,lavish=False,qualified_employee_recreation=False,
                other_tax_exception=False,mixed_entertainment=False)
    result = evaluator.evaluate(c)
    assert result.tax.verdict == "undetermined"
    assert any(q["fact"]=="business_purpose" for q in result.questions)
    assert result.company.verdict == "not_applicable"


def test_receipt_boundary_evidence_and_historical_approval(evaluator):
    c = changed(case(purchase_date="2026-08-01"),receipt_required=True)
    timely = c.model_copy(update={"receipts":[Receipt(evidence_id="r",submitted_date="2026-09-30")]})
    assert evaluator.evaluate(timely,suggestions=False).company.verdict == "compliant"
    c = case(amount_cents=4800,approvals=[
        Approval(evidence_id="early",approver_id="manager",approved=True,approved_at="2026-09-30T12:00:00Z"),
        Approval(evidence_id="late",approver_id="manager",approved=True,approved_at="2026-10-02T12:00:00Z")])
    assert evaluator.evaluate(c,suggestions=False).company.verdict == "compliant"


def test_ledger_cache_invalidation_same_version_policy_change():
    service = BackendService()
    c = case(amount_cents=3501)
    assert service.ledger([c])[0]["audit_result"] is None
    assert service.check(c).company.verdict == "violation"
    assert service.ledger([c])[0]["audit_result"] is not None
    changed_case = c.model_copy(update={"amount_cents":3500})
    assert service.ledger([changed_case])[0]["audit_result"] is None
    pack = load_policy_pack()
    pack["rules"][0]["when"] = {"gt":[{"fact":"amount_cents"},5000]}
    service.evaluator = PolicyEvaluator(pack)
    assert service.ledger([c])[0]["audit_result"] is None
    assert service.check(c).company.verdict == "not_applicable"


@pytest.fixture(scope="module")
def fixtures(tmp_path_factory):
    output = tmp_path_factory.mktemp("fixtures")
    records = [case(case_id=f"company-072:b{i}",origin="original",amount_cents=4800,facts={}) for i in range(10)]
    records += [case(case_id=f"company-001:b{i}",company_id="company-001",origin="original",amount_cents=4800,facts={}) for i in range(30)]
    build_fixtures(records,output)
    return output


def test_draft_fixture_contract_and_all_expected_outcomes(fixtures,evaluator):
    cases = [PurchaseCase.model_validate(row) for row in read_jsonl(fixtures/"cases.jsonl")]
    labels,splits = read_jsonl(fixtures/"labels.jsonl"),read_jsonl(fixtures/"splits.jsonl")
    li,_ = validate_dataset(cases,labels,splits)
    assert len(cases)==200
    assert sum(c.origin=="original" for c in cases)==40
    assert sum(s["split"]=="tuning" for s in splits)==50
    # Variant wording changes no facts: evaluate each independent synthetic scenario once.
    selected = [c for c in cases if c.origin=="synthetic" and c.case_id.endswith(":0")]
    for c in selected:
        result = evaluator.evaluate(c,suggestions=False)
        assert result.status=="ok"
        for layer in ("company","tax"):
            actual = getattr(result,layer)
            assert actual.verdict==li[c.case_id][f"{layer}_verdict"], (c.case_id,layer,result)
            assert set(actual.violated_rule_ids)==set(li[c.case_id][f"{layer}_rule_ids"])
    assert all(label["review_status"]=="draft" for label in labels)
    payload = model_input(selected[0])
    assert not SEMANTIC_FACTS.intersection(payload["facts"])
    assert not {"rationale","review_status","split","group_id","expected_verdict"}.intersection(payload)
    bad_splits = deepcopy(splits)
    bad_splits[-1]["split"]="tuning"
    with pytest.raises(ValueError,match="leakage"): validate_dataset(cases,labels,bad_splits)


def mini_dataset():
    c = case()
    label = dict(case_id=c.case_id,company_verdict="not_applicable",company_rule_ids=[],tax_verdict="not_applicable",tax_rule_ids=[],review_status="draft",rationale="No applicable rule")
    split = dict(case_id=c.case_id,group_id="one",split="test",origin="synthetic")
    return [c],[label],[split]


def test_offline_metrics_and_failures(tmp_path):
    cases,labels,splits = mini_dataset()
    summary = run_benchmark(cases,labels,splits,tmp_path,methods=("keyword","gemini_judge"))
    keyword = summary["methods"]["keyword"]["overall"]
    assert keyword["accuracy"]==keyword["coverage"]==keyword["repeatability"]==1
    assert keyword["cost_per_1000_usd"]==0
    missing = summary["methods"]["gemini_judge"]["overall"]
    assert missing["coverage"]==0 and missing["accuracy"] is None and missing["repeatability"] is None
    def failed(*args): raise RuntimeError("adapter failed")
    with pytest.raises(ValueError,match="allow_live"):
        run_benchmark(cases,labels,splits,tmp_path,methods=("gemini_judge",),adapters={"gemini_judge":failed})
    summary = run_benchmark(cases,labels,splits,tmp_path,methods=("gemini_judge",),adapters={"gemini_judge":failed},allow_live=True)
    assert summary["methods"]["gemini_judge"]["overall"]["status_counts"]=={"error":3}


def test_recorded_extraction_runs_and_invalid_predictions(tmp_path):
    cases,labels,splits = mini_dataset()
    path = tmp_path/"input.jsonl"
    record = dict(case_id=cases[0].case_id,method="jev_facts_z3",run=1,model="jev-test",inference_backend="recorded_jev",
                  facts={"expense_kind":{"value":"office","source":"extractor","probability":.99}},latency_ms=12,cost_usd=.001)
    write_jsonl(path,[record])
    summary = run_benchmark(cases,labels,splits,tmp_path/"out",methods=("jev_facts_z3",),prediction_paths=[path])
    metrics = summary["methods"]["jev_facts_z3"]["overall"]
    assert metrics["accuracy"]==1 and metrics["coverage"]==pytest.approx(1/3)
    assert metrics["repeatability"] is None and metrics["cost_per_1000_usd"]==1
    invalid = {**record,"facts":{"pre_approved":{"value":True,"source":"model"}}}
    write_jsonl(path,[invalid])
    summary = run_benchmark(cases,labels,splits,tmp_path/"out",methods=("jev_facts_z3",),prediction_paths=[path])
    assert summary["methods"]["jev_facts_z3"]["overall"]["status_counts"]=={"error":1,"unavailable":2}


def test_gold_semantics_are_never_used_for_missing_or_low_confidence_predictions(tmp_path):
    cases,labels,splits = mini_dataset()
    path = tmp_path/"input.jsonl"
    record = dict(case_id=cases[0].case_id,method="gemini_facts_z3",model="test-model",inference_backend="recorded_test",
                  facts={"expense_kind":{"value":"office","source":"extractor","probability":.1}})
    write_jsonl(path,[{**record,"run":i} for i in (1,2,3)])
    summary = run_benchmark(cases,labels,splits,tmp_path/"out",methods=("gemini_facts_z3",),prediction_paths=[path])
    rows = read_jsonl(tmp_path/"out"/"predictions.jsonl")
    assert all(r["judgment"]["tax_verdict"]=="undetermined" for r in rows)
    assert summary["methods"]["gemini_facts_z3"]["overall"]["median_latency_ms"] is None
    assert summary["methods"]["gemini_facts_z3"]["overall"]["cost_per_1000_usd"] is None


def test_metrics_known_counts():
    labels = {"x":{"company_verdict":"violation","company_rule_ids":["a","b"],"tax_verdict":"not_applicable","tax_rule_ids":[],"review_status":"draft"}}
    rows = [{"case_id":"x","run":i,"status":"ok","model":"test","inference_backend":"local",
        "judgment":{"company_verdict":"violation","company_rule_ids":["a","wrong"],"tax_verdict":"not_applicable","tax_rule_ids":[]},
        "latency_ms":ms,"cost_usd":.002} for i,ms in enumerate([1,2,100],1)]
    summary = summarize(rows,labels)
    assert summary["median_latency_ms"]==2 and summary["p95_latency_ms"]==100
    assert summary["company"]["citations"]["f1"]==.5
    assert summary["citations"]["f1"]==.5
    assert summary["cost_per_1000_usd"]==2 and summary["repeatability"]==1
    rows[-1]["model"] = "different-model"
    assert summarize(rows,labels)["repeatability"] is None


def test_gemini_adapter_mock_and_no_fallback():
    judgment = dict(company_verdict="not_applicable",company_rule_ids=[],tax_verdict="not_applicable",tax_rule_ids=[])
    def respond(request):
        assert request.headers["x-goog-api-key"]=="test-key"
        body = json.loads(request.content)
        assert body["generationConfig"]["responseMimeType"]=="application/json"
        return httpx.Response(200,json={"candidates":[{"content":{"parts":[{"text":json.dumps(judgment)}]}}],
            "usageMetadata":{"promptTokenCount":100,"candidatesTokenCount":20,"thoughtsTokenCount":5}})
    adapter = GeminiJudge(model="test-model",api_key="test-key",input_per_million=1,output_per_million=2,transport=httpx.MockTransport(respond))
    result = adapter(model_input(case()),load_policy_pack(),1)
    assert result.cost_usd==pytest.approx(.00015)
    broken = GeminiJudge(model="test-model",api_key="test-key",transport=httpx.MockTransport(lambda _:httpx.Response(429)))
    with pytest.raises(RuntimeError,match="429"): broken(model_input(case()),load_policy_pack(),1)
