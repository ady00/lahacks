"""
Persistent rule store for managing active corporate policies and accounting rules.
"""

import json
import os
from pathlib import Path
from typing import List, Optional, Tuple

from .models import ProofResult, ProofStatus, Z3RuleParameters
from .jev.classifier import JevRuleClassifier
from .z3_engine.proof_engine import Z3SpendProofEngine

DEFAULT_STORE_PATH = Path(os.environ.get("JEV_Z3_STORE_PATH", "policy_store.json"))

DEFAULT_POLICIES = [
    "Meals and entertainment expenses over $75 require an itemized receipt and manager approval.",
    "Software and SaaS subscriptions exceeding $500 per month must be billed to Engineering and approved by a VP.",
    "Meals and dining exceeding $60 per attendee require an itemized attendees list.",
    "Contractor and consultant payments above $10,000 require purchase order matching and an active W-9 tax form.",
    "QuickBooks rule: Categorize all Uber and Lyft rides under $100 to Account 6200 and Class Sales.",
]


class PolicyStore:
    """
    Manages loading, saving, and verifying active corporate spend and accounting rules.
    """

    def __init__(self, store_path: Optional[Path] = None):
        self.store_path = store_path or DEFAULT_STORE_PATH
        self.classifier = JevRuleClassifier()
        self.proof_engine = Z3SpendProofEngine()
        self._ensure_store()

    def _ensure_store(self) -> None:
        if not self.store_path.exists():
            # Initialize with standard corporate default rules
            rules = []
            for i, text in enumerate(DEFAULT_POLICIES, 1):
                p = self.classifier.classify_rule(text, rule_id=f"POL-{i:03d}")
                rules.append(p)
            self.save_rules(rules)

    def list_rules(self) -> List[Z3RuleParameters]:
        if not self.store_path.exists():
            return []
        with open(self.store_path, "r") as f:
            data = json.load(f)
        return [Z3RuleParameters(**item) for item in data]

    def save_rules(self, rules: List[Z3RuleParameters]) -> None:
        data = [r.model_dump() for r in rules]
        with open(self.store_path, "w") as f:
            json.dump(data, f, indent=2)

    def add_rule(
        self,
        rule_text: str,
        rule_id: Optional[str] = None,
        enforce_consistency: bool = True,
    ) -> Tuple[Z3RuleParameters, Optional[ProofResult]]:
        """
        Classifies the natural language rule with Jev, checks consistency against
        all existing rules with Z3, and stores it if consistent.
        """
        existing_rules = self.list_rules()
        new_id = rule_id or f"POL-{(len(existing_rules) + 1):03d}"
        new_param = self.classifier.classify_rule(rule_text, rule_id=new_id)

        # Check for contradictions against all active rules in Z3
        if enforce_consistency:
            for existing in existing_rules:
                conflict_res = self.proof_engine.prove_policy_consistency(new_param, existing)
                if conflict_res.status == ProofStatus.INCONSISTENT_POLICY:
                    return new_param, conflict_res

        # Append and save
        existing_rules.append(new_param)
        self.save_rules(existing_rules)
        return new_param, None

    def clear(self) -> None:
        if self.store_path.exists():
            self.store_path.unlink()
        self._ensure_store()

