"""Stateless evaluation plus an optional in-process audit cache (not persistence)."""
from collections import Counter
from .models import Approval, Fact, PurchaseCase, Receipt, digest
from .policy import PolicyEvaluator, fields


class BackendService:
    def __init__(self, evaluator=None):
        self.evaluator = evaluator or PolicyEvaluator()
        self._cache = {}

    def check(self, case: PurchaseCase):
        key = (case.company_id, case.case_id, self.evaluator.version, self.evaluator.policy_hash, digest(case))
        if key not in self._cache:
            self._cache[key] = self.evaluator.evaluate(case)
        return self._cache[key].model_copy(deep=True)

    def ledger(self, cases):
        """Normalized purchases plus matching cached results, without starting an audit."""
        rows = []
        for case in cases:
            key = (case.company_id, case.case_id, self.evaluator.version, self.evaluator.policy_hash, digest(case))
            result = self._cache.get(key)
            rows.append({"purchase":case.model_dump(mode="json"),
                         "audit_result":result.model_dump(mode="json") if result else None})
        return rows

    def answer(self, case: PurchaseCase, answers: dict[str, Fact]):
        protected = {"pre_approved", "receipt_timely", "receipt_attached"}
        if protected.intersection(answers):
            raise ValueError("Approval and receipt facts require evidence records, not a user answer")
        updated = PurchaseCase.model_validate({**case.model_dump(), "facts": {**case.facts, **answers}})
        return updated, self.check(updated)

    def approve(self, case: PurchaseCase, approval: Approval):
        # Authentication, manager authorization and persistence belong to the API.
        updated = PurchaseCase.model_validate({**case.model_dump(), "approvals": [*case.approvals, approval]})
        return updated, self.check(updated)

    def attach_receipt(self, case: PurchaseCase, receipt: Receipt):
        updated = PurchaseCase.model_validate({**case.model_dump(), "receipts": [*case.receipts, receipt]})
        return updated, self.check(updated)

    def audit(self, cases):
        results = [self.check(case) for case in cases]
        ok = [r for r in results if r.status == "ok"]
        decidable = sum(r.company.verdict in {"compliant", "violation"} for r in ok)
        relevant = set().union(*(fields(r["when"]) | fields(r["require"]) for r in self.evaluator.pack["rules"]))
        known = sum(sum(key in r.facts and r.facts[key].value is not None for key in relevant) for r in results)
        missing = Counter(key for r in results for key in relevant if key not in r.facts or r.facts[key].value is None)
        return {"schema_version": "1", "policy_version": self.evaluator.version, "policy_hash": self.evaluator.policy_hash,
                "total": len(results), "status_counts": dict(Counter(r.status for r in results)),
                "company_verdict_counts": dict(Counter(r.company.verdict for r in ok)),
                "tax_verdict_counts": dict(Counter(r.tax.verdict for r in ok)),
                "decidable_company_coverage": decidable / len(results) if results else None,
                "evidence_coverage": known / (len(results)*len(relevant)) if results and relevant else None,
                "missing_evidence_counts": dict(sorted(missing.items())),
                "results": [r.model_dump(mode="json") for r in results]}
