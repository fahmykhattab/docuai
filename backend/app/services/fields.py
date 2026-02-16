from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class ExtractedField:
    name: str
    value: str
    type: str  # "date", "amount", "invoice_number", "iban", "name", "address", "string"


class FieldExtractor:
    """Extracts structured fields from document text using Ollama."""

    def extract_fields(self, text: str) -> List[ExtractedField]:
        """Extract structured fields (dates, amounts, IBANs, etc.) from text."""
        if not text or not text.strip():
            return []

        truncated = text[:4000]

        prompt = self._build_prompt(truncated)

        try:
            response = httpx.post(
                f"{settings.OLLAMA_URL}/api/generate",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()
            raw = data.get("response", "")
            return self._parse_response(raw)
        except httpx.ConnectError:
            logger.warning("Ollama not available for field extraction")
            return self._fallback_extract(text)
        except Exception as e:
            logger.exception("Field extraction error: %s", e)
            return self._fallback_extract(text)

    def _build_prompt(self, text: str) -> str:
        return f"""Analyze the following document text and extract structured fields.

Look for these types of information:
- Dates (document date, due date, etc.)
- Amounts/prices (total, subtotal, tax)
- Invoice/reference numbers
- IBAN or bank account numbers
- Person names
- Company names
- Addresses

Respond ONLY with a valid JSON object containing a "fields" array. Each field should have:
- "name": descriptive field name (e.g., "Invoice Date", "Total Amount", "IBAN")
- "value": the extracted value as a string
- "type": one of "date", "amount", "invoice_number", "iban", "name", "address", "string"

Example response:
{{"fields": [{{"name": "Invoice Date", "value": "2024-01-15", "type": "date"}}, {{"name": "Total Amount", "value": "1,234.56 EUR", "type": "amount"}}]}}

Document text:
---
{text}
---

JSON response:"""

    def _parse_response(self, raw: str) -> List[ExtractedField]:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                except json.JSONDecodeError:
                    logger.warning("Could not parse field extraction response")
                    return []
            else:
                return []

        fields_data = data.get("fields", [])
        if not isinstance(fields_data, list):
            return []

        result: list[ExtractedField] = []
        for f in fields_data:
            if isinstance(f, dict) and "name" in f and "value" in f:
                result.append(ExtractedField(
                    name=str(f["name"]),
                    value=str(f["value"]),
                    type=str(f.get("type", "string")),
                ))
        return result

    def _fallback_extract(self, text: str) -> List[ExtractedField]:
        """Regex-based fallback when Ollama is unavailable."""
        fields: list[ExtractedField] = []

        # IBAN
        iban_pattern = r"\b[A-Z]{2}\d{2}[\s]?[\dA-Z]{4}[\s]?[\dA-Z]{4}[\s]?[\dA-Z]{4}[\s]?[\dA-Z]{0,16}\b"
        for match in re.finditer(iban_pattern, text):
            fields.append(ExtractedField(name="IBAN", value=match.group().strip(), type="iban"))

        # Dates (various formats)
        date_patterns = [
            (r"\b\d{4}-\d{2}-\d{2}\b", "Date"),
            (r"\b\d{2}[./]\d{2}[./]\d{4}\b", "Date"),
            (r"\b\d{2}\.\s?\w+\s?\d{4}\b", "Date"),
        ]
        for pattern, name in date_patterns:
            for match in re.finditer(pattern, text):
                fields.append(ExtractedField(name=name, value=match.group().strip(), type="date"))

        # Amounts (EUR, USD, numbers with currency)
        amount_pattern = r"(?:EUR|USD|€|\$)\s?[\d.,]+|\b[\d.,]+\s?(?:EUR|USD|€|\$)"
        for match in re.finditer(amount_pattern, text):
            fields.append(ExtractedField(name="Amount", value=match.group().strip(), type="amount"))

        # Invoice numbers
        inv_pattern = r"(?:Invoice|Rechnung|Faktura|INV)[#:\s-]*(\S+)"
        for match in re.finditer(inv_pattern, text, re.IGNORECASE):
            fields.append(ExtractedField(name="Invoice Number", value=match.group(1).strip(), type="invoice_number"))

        return fields
