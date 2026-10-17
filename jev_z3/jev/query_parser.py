"""
Natural language purchase query parser using Jev 'System One' classification.
Converts client purchase queries into structured Transaction intents for Z3 verification.
"""

import re
from typing import Optional
from pydantic import BaseModel, Field

from ..models import SpendCategory
from .client import JevClient
from .schema import JEV_SPEND_RULE_QUESTIONS


class PurchaseIntent(BaseModel):
    """
    Extracted parameters from a client's natural language purchase query.
    """
    raw_query: str
    amount: float
    category: SpendCategory = SpendCategory.GENERAL_SPEND
    department: str = "General"
    vendor: str = "Unspecified Vendor"
    attendee_count: int = 1
    description: str = ""
    currency: str = "USD"


class QueryParser:
    """
    Parses client purchase intent queries using Jev classification and regex extractors.
    """

    def __init__(self, client: Optional[JevClient] = None):
        self.client = client or JevClient()

    def parse_query(self, query_text: str) -> PurchaseIntent:
        """
        Parses a natural language query like:
        'Can I buy a $650 Datadog monitoring subscription for Engineering?'
        """
        # 1. Evaluate with Jev for Category and Department
        jev_response = self.client.system_one(
            state=query_text,
            questions={
                "category": JEV_SPEND_RULE_QUESTIONS["category"],
                "target_department": JEV_SPEND_RULE_QUESTIONS["target_department"],
            },
        )
        answers = jev_response.get("answers", {})

        cat_choice = answers.get("category", {}).get("choice", "general_spend")
        dept_choice = answers.get("target_department", {}).get("choice", "General")
        dept_val = dept_choice.capitalize() if dept_choice != "any" else "General"

        # 2. Extract Amount
        amount = self._extract_amount(query_text)

        # 3. Extract Vendor
        vendor = self._extract_vendor(query_text)

        # 4. Extract Attendees count
        attendees = self._extract_attendees(query_text)

        return PurchaseIntent(
            raw_query=query_text,
            amount=amount,
            category=SpendCategory(cat_choice),
            department=dept_val,
            vendor=vendor,
            attendee_count=attendees,
            description=query_text,
        )

    def _extract_amount(self, text: str) -> float:
        amt_match = re.search(r"\$\s*([0-9,]+(?:\.[0-9]+)?)", text)
        if amt_match:
            return float(amt_match.group(1).replace(",", ""))

        word_match = re.search(r"([0-9,]+(?:\.[0-9]+)?)\s*(?:dollars|usd|bucks)", text, re.IGNORECASE)
        if word_match:
            return float(word_match.group(1).replace(",", ""))

        # Fallback to standalone number
        num_match = re.search(r"\b([0-9]+(?:\.[0-9]{2})?)\b", text)
        if num_match:
            return float(num_match.group(1))

        return 0.0

    def _extract_vendor(self, text: str) -> str:
        for known in ["Datadog", "Amazon", "Delta", "United", "Uber", "Lyft", "AWS", "Google Cloud", "Figma", "Slack", "Nobu", "Chipotle", "Salesforce"]:
            if re.search(r"\b" + re.escape(known) + r"\b", text, re.IGNORECASE):
                return known

        match = re.search(r"(?:at|from|with|vendor)\s+([A-Z][a-zA-Z0-9&]+)", text)
        if match:
            return match.group(1)

        return "Unspecified Vendor"

    def _extract_attendees(self, text: str) -> int:
        match = re.search(r"([0-9]+)\s*(?:people|clients|guests|attendees|colleagues|coworkers)", text, re.IGNORECASE)
        if match:
            count = int(match.group(1))
            # If user says "take 3 clients", total people = user + 3 = 4
            if "take" in text.lower() or "with" in text.lower():
                return count + 1
            return count

        for word, val in [("one", 1), ("two", 2), ("three", 3), ("four", 4), ("five", 5), ("six", 6)]:
            if re.search(r"\b" + word + r"\s+(?:people|clients|guests|attendees)", text, re.IGNORECASE):
                return val + 1 if "take" in text.lower() or "with" in text.lower() else val

        return 1

