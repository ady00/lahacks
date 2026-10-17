"""
Jev-based rule classifier that converts natural language spend and accounting rules
into typed Z3RuleParameters for formal verification.
"""

import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from ..models import (
    ComparisonOperator,
    RuleAction,
    RuleDomain,
    SpendCategory,
    TargetScope,
    Z3RuleParameters,
)
from .client import JevClient
from .schema import JEV_SPEND_RULE_QUESTIONS


class JevRuleClassifier:
    """
    Translates natural language corporate expense policies, QuickBooks rules,
    and spend controls into formal parameters consumable by Z3 SMT solver.
    """

    def __init__(self, client: Optional[JevClient] = None):
        self.client = client or JevClient()

    def classify_rule(self, rule_text: str, rule_id: Optional[str] = None) -> Z3RuleParameters:
        """
        Execute Jev 'System One' classification on natural language rule text
        and construct the formal Z3 parameter object.
        """
        rule_id = rule_id or f"rule_{uuid.uuid4().hex[:8]}"

        # 1. Run Jev structured evaluation
        jev_response = self.client.system_one(
            state=rule_text,
            questions=JEV_SPEND_RULE_QUESTIONS,
        )
        answers = jev_response.get("answers", {})

        # 2. Extract classified categorical fields
        domain_choice = answers.get("rule_domain", {}).get("choice", "expense_policy")
        scope_choice = answers.get("target_scope", {}).get("choice", "single_transaction")
        category_choice = answers.get("category", {}).get("choice", "general_spend")
        operator_choice = answers.get("operator", {}).get("choice", "always")
        action_choice = answers.get("action", {}).get("choice", "require_approval")
        dept_choice = answers.get("target_department", {}).get("choice", "any")
        qb_choice = answers.get("qb_account", {}).get("choice", "unassigned")

        # 3. Extract calibrated boolean predicates (noul answers > 0.50)
        req_receipt = answers.get("requires_receipt", {}).get("noul", 0.0) >= 0.50
        req_manager = answers.get("requires_manager_approval", {}).get("noul", 0.0) >= 0.50
        req_vp = answers.get("requires_vp_approval", {}).get("noul", 0.0) >= 0.50
        req_po = answers.get("requires_purchase_order", {}).get("noul", 0.0) >= 0.50
        req_attendees = answers.get("requires_itemized_attendees", {}).get("noul", 0.0) >= 0.50
        req_w9 = answers.get("requires_w9", {}).get("noul", 0.0) >= 0.50
        req_audit = answers.get("requires_compliance_audit", {}).get("noul", 0.0) >= 0.50

        # 4. Extract numeric thresholds and ranges
        threshold, upper_threshold = self._extract_amounts(rule_text)
        currency = self._extract_currency(rule_text)
        vendor = self._extract_vendor(rule_text)
        keywords = self._extract_keywords(rule_text)
        window_hours, max_agg = self._extract_split_params(rule_text)

        # 5. Check accounting balance requirements
        enforce_balance = any(
            k in rule_text.lower()
            for k in ["debit must equal credit", "debits equal credits", "double entry", "balance sheet", "sum(line_items)"]
        )

        # 6. Map operator enum
        operator_map = {
            "greater_than": ComparisonOperator.GREATER_THAN,
            "greater_equal": ComparisonOperator.GREATER_EQUAL,
            "less_than": ComparisonOperator.LESS_THAN,
            "less_equal": ComparisonOperator.LESS_EQUAL,
            "between": ComparisonOperator.BETWEEN,
            "equals": ComparisonOperator.EQUALS,
            "always": ComparisonOperator.ALWAYS,
        }
        mapped_op = operator_map.get(operator_choice, ComparisonOperator.ALWAYS)

        # If an amount threshold was found but operator came out as always, infer operator
        if threshold is not None and mapped_op == ComparisonOperator.ALWAYS:
            if any(k in rule_text.lower() for k in ["over", "above", "exceeding", "more than", ">"]):
                mapped_op = ComparisonOperator.GREATER_THAN
            elif any(k in rule_text.lower() for k in ["at least", ">="]):
                mapped_op = ComparisonOperator.GREATER_EQUAL
            elif any(k in rule_text.lower() for k in ["under", "less than", "below", "<"]):
                mapped_op = ComparisonOperator.LESS_THAN
            elif any(k in rule_text.lower() for k in ["up to", "at most", "<="]):
                mapped_op = ComparisonOperator.LESS_EQUAL
            else:
                mapped_op = ComparisonOperator.GREATER_THAN

        # Aggregate confidence metrics
        confidences = {
            k: v.get("confidence") or v.get("noul") or 0.0
            for k, v in answers.items()
        }

        # QB Class extraction (e.g., Class 'Sales' or 'Engineering')
        qb_class = None
        class_match = re.search(r"class\s+['\"]?([a-zA-Z\s]+)['\"]?", rule_text, re.IGNORECASE)
        if class_match:
            qb_class = class_match.group(1).strip()
        elif dept_choice != "any":
            qb_class = dept_choice.capitalize()

        return Z3RuleParameters(
            rule_id=rule_id,
            raw_text=rule_text,
            domain=RuleDomain(domain_choice),
            scope=TargetScope(scope_choice),
            category=SpendCategory(category_choice),
            operator=mapped_op,
            threshold_amount=threshold,
            upper_threshold_amount=upper_threshold,
            currency=currency,
            vendor_pattern=vendor,
            description_keywords=keywords,
            action=RuleAction(action_choice),
            requires_receipt=req_receipt,
            requires_manager_approval=req_manager,
            requires_vp_approval=req_vp,
            requires_purchase_order=req_po,
            requires_itemized_attendees=req_attendees,
            requires_w9=req_w9,
            requires_compliance_audit=req_audit,
            target_department=dept_choice if dept_choice != "any" else None,
            qb_account=qb_choice if qb_choice != "unassigned" else None,
            qb_class=qb_class,
            enforce_debit_credit_balance=enforce_balance,
            max_aggregate_amount=max_agg or threshold if scope_choice == "daily_aggregate" else None,
            aggregate_window_hours=window_hours,
            confidence_scores=confidences,
        )

    def _extract_amounts(self, text: str) -> Tuple[Optional[float], Optional[float]]:
        # Check range pattern: "between $X and $Y"
        range_match = re.search(r"between\s+\$?([0-9,]+(?:\.[0-9]+)?)\s+and\s+\$?([0-9,]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
        if range_match:
            low = float(range_match.group(1).replace(",", ""))
            high = float(range_match.group(2).replace(",", ""))
            return low, high

        # General currency amounts
        amounts = re.findall(r"\$\s*([0-9,]+(?:\.[0-9]{1,2})?)", text)
        if amounts:
            nums = [float(a.replace(",", "")) for a in amounts]
            if len(nums) == 1:
                return nums[0], None
            return nums[0], nums[1]

        # Plain number followed by dollars or USD
        word_match = re.findall(r"([0-9,]+(?:\.[0-9]+)?)\s*(?:dollars|usd)", text, re.IGNORECASE)
        if word_match:
            nums = [float(w.replace(",", "")) for w in word_match]
            if len(nums) == 1:
                return nums[0], None
            return nums[0], nums[1]

        return None, None

    def _extract_currency(self, text: str) -> str:
        if "eur" in text.lower() or "€" in text:
            return "EUR"
        if "gbp" in text.lower() or "£" in text:
            return "GBP"
        return "USD"

    def _extract_vendor(self, text: str) -> Optional[str]:
        match = re.search(r"(?:vendor|merchant)\s*(?:is|equals|named|from)?\s*['\"]?([A-Za-z0-9\s&]+?)['\"]?(?:\s+and|\s+or|\s+must|\s+requires|\s+is|\s*[,.]|$)", text, re.IGNORECASE)
        if match:
            v = match.group(1).strip()
            if v and v.lower() not in ["any", "the", "a"]:
                return v

        # Common known vendors
        for known in ["Amazon", "Delta", "United", "Uber", "Lyft", "AWS", "Google Cloud", "Salesforce", "Slack"]:
            if re.search(r"\b" + re.escape(known) + r"\b", text, re.IGNORECASE):
                return known
        return None

    def _extract_keywords(self, text: str) -> List[str]:
        match = re.search(r"description\s+contains\s+['\"]?([A-Za-z0-9\s/]+)['\"]?", text, re.IGNORECASE)
        if match:
            return [k.strip() for k in match.group(1).split() if k.strip()]
        return []

    def _extract_split_params(self, text: str) -> Tuple[Optional[int], Optional[float]]:
        hours = None
        h_match = re.search(r"([0-9]+)\s*(?:-| )?hour", text, re.IGNORECASE)
        if h_match:
            hours = int(h_match.group(1))
        elif "24-hour" in text.lower() or "daily" in text.lower():
            hours = 24

        max_agg = None
        agg_match = re.search(r"totaling\s*(?:more than|over)?\s*\$?([0-9,]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
        if agg_match:
            max_agg = float(agg_match.group(1).replace(",", ""))

        return hours, max_agg

