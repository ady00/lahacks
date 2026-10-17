"""Reproducible commands independent of HTTP route readiness."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .evaluation import GeminiJudge, METHODS, run_benchmark
from .fixtures import build_fixtures, read_jsonl, write_json, write_jsonl
from .loader import load_archive, load_records
from .policy import PolicyEvaluator, load_policy_pack
from .service import BackendService


def read_cases(path):
    return load_records(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Data, policy scenarios and benchmarks for Proof of Purchase")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest", help="Normalize bank-linked purchases directly from the archive")
    ingest.add_argument("--archive", default="data/hackathon-100-participant.tar.gz")
    ingest.add_argument("--company", default="company-072", help="Company ID or all")
    ingest.add_argument("--output", default="artifacts/backend/ledger")
    fixtures = commands.add_parser("fixtures", help="Build 200 draft-labeled cases from all-company normalized records")
    fixtures.add_argument("--records", required=True)
    fixtures.add_argument("--company", default="company-072")
    fixtures.add_argument("--output", default="artifacts/backend/fixtures")
    build = commands.add_parser("build", help="Ingest/validate all companies, build fixtures and export policy")
    build.add_argument("--archive", default="data/hackathon-100-participant.tar.gz")
    build.add_argument("--company", default="company-072")
    build.add_argument("--output", default="artifacts/backend")
    for name in ("check", "audit"):
        command = commands.add_parser(name)
        command.add_argument("--cases", required=True, help="PurchaseCase JSONL")
        command.add_argument("--policy", help="Optional reviewed JSON policy pack")
        command.add_argument("--output", default=f"artifacts/backend/{name}.json")
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--fixtures", default="artifacts/backend/fixtures")
    evaluate.add_argument("--output", default="artifacts/backend/evaluation")
    evaluate.add_argument("--methods", nargs="+", choices=METHODS, default=["keyword"])
    evaluate.add_argument("--predictions", action="append", default=[])
    evaluate.add_argument("--allow-live", action="store_true")
    evaluate.add_argument("--gemini-model", default=os.getenv("GEMINI_MODEL"))
    evaluate.add_argument("--input-per-million", type=float)
    evaluate.add_argument("--output-per-million", type=float)
    evaluate.add_argument("--confidence-threshold", type=float, default=.85)
    evaluate.add_argument("--policy")
    args = parser.parse_args(argv)
    output = Path(args.output)
    if args.command in {"ingest", "build"}:
        loaded = load_archive(args.archive, "all" if args.command=="build" else args.company,
                              progress=lambda cid, counts: print(f"{cid}: {counts['cash_purchase_cases']} purchases", flush=True))
        records_dir = output/"ledger" if args.command=="build" else output
        records_dir.mkdir(parents=True,exist_ok=True)
        write_jsonl(records_dir/"purchases.jsonl", loaded.purchases)
        write_jsonl(records_dir/"employees.jsonl", loaded.employees)
        write_json(records_dir/"manifest.json", loaded.manifest)
        if args.command == "build":
            write_jsonl(output/"demo_ledger.jsonl", [c for c in loaded.purchases if c.company_id==args.company])
            build_fixtures(loaded.purchases,output/"fixtures",company=args.company)
            write_json(output/"policy.json",load_policy_pack())
        print(json.dumps({"companies":loaded.manifest["company_count"],"purchases":len(loaded.purchases),"output":str(output)}))
    elif args.command == "fixtures":
        print(json.dumps(build_fixtures(read_cases(args.records),output,company=args.company)["counts"]))
    elif args.command in {"audit", "check"}:
        pack = json.loads(Path(args.policy).read_text(encoding="utf-8")) if args.policy else None
        service = BackendService(PolicyEvaluator(pack))
        cases = read_cases(args.cases)
        result = service.audit(cases) if args.command=="audit" else [service.check(c).model_dump(mode="json") for c in cases]
        output.parent.mkdir(parents=True, exist_ok=True)
        write_json(output,result)
        print(f"Wrote {len(cases)} evaluated cases to {output}")
    else:
        fixture_dir = Path(args.fixtures)
        adapters = {}
        if args.allow_live:
            if "gemini_judge" not in args.methods:
                parser.error("--allow-live requires the explicitly selected gemini_judge method; extraction adapters use the Python interface")
            adapters["gemini_judge"] = GeminiJudge(model=args.gemini_model,api_key=os.getenv("GEMINI_API_KEY",""),
                input_per_million=args.input_per_million,output_per_million=args.output_per_million)
        pack = json.loads(Path(args.policy).read_text(encoding="utf-8")) if args.policy else None
        summary = run_benchmark(read_cases(fixture_dir/"cases.jsonl"),read_jsonl(fixture_dir/"labels.jsonl"),
            read_jsonl(fixture_dir/"splits.jsonl"),output,methods=args.methods,prediction_paths=args.predictions,
            adapters=adapters,allow_live=args.allow_live,evaluator=PolicyEvaluator(pack),confidence_threshold=args.confidence_threshold)
        print(json.dumps({m:v["overall"] for m,v in summary["methods"].items()},indent=2))


if __name__ == "__main__":
    main()
