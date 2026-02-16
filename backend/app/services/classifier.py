from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class ClassificationResult:
    title: str = ""
    tags: List[str] = field(default_factory=list)
    document_type: str = ""
    correspondent: str = ""
    date: Optional[str] = None
    summary: str = ""


class ClassifierService:
    """Uses Ollama LLM to classify documents and suggest metadata."""

    def classify(
        self,
        text: str,
        existing_tags: List[str],
        existing_types: List[str],
        existing_correspondents: List[str],
    ) -> ClassificationResult:
        if not text or not text.strip():
            return ClassificationResult()

        # Truncate text to avoid exceeding model context
        truncated = text[:4000]

        prompt = self._build_prompt(truncated, existing_tags, existing_types, existing_correspondents)

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
            raw_response = data.get("response", "")
            return self._parse_response(raw_response)
        except httpx.ConnectError:
            logger.warning("Ollama not available for classification")
            return ClassificationResult(title=self._fallback_title(text))
        except Exception as e:
            logger.exception("Classification error: %s", e)
            return ClassificationResult(title=self._fallback_title(text))

    def _build_prompt(
        self,
        text: str,
        existing_tags: List[str],
        existing_types: List[str],
        existing_correspondents: List[str],
    ) -> str:
        tags_hint = f"Existing tags: {', '.join(existing_tags)}" if existing_tags else "No existing tags."
        types_hint = f"Existing document types: {', '.join(existing_types)}" if existing_types else "No existing types."
        corr_hint = f"Existing correspondents: {', '.join(existing_correspondents)}" if existing_correspondents else "No existing correspondents."

        return f"""Analyze the following document text and provide classification metadata.

{tags_hint}
{types_hint}
{corr_hint}

Respond ONLY with a valid JSON object with these exact keys:
- "title": A concise descriptive title for this document
- "tags": An array of tag names (reuse existing tags when appropriate, or suggest new ones)
- "document_type": The type of document (e.g., "Invoice", "Receipt", "Contract", "Letter", "Report"). Reuse existing types when appropriate.
- "correspondent": The sender/author/company name. Reuse existing correspondents when appropriate.
- "date": The document date in YYYY-MM-DD format, or null if not found
- "summary": A brief 1-2 sentence summary

Document text:
---
{text}
---

JSON response:"""

    def _parse_response(self, raw: str) -> ClassificationResult:
        # Try to extract JSON from the response
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Try to find JSON in the response
            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                except json.JSONDecodeError:
                    logger.warning("Could not parse classification response: %s", raw[:200])
                    return ClassificationResult()
            else:
                logger.warning("No JSON found in classification response: %s", raw[:200])
                return ClassificationResult()

        return ClassificationResult(
            title=str(data.get("title", "")),
            tags=[str(t) for t in data.get("tags", []) if t],
            document_type=str(data.get("document_type", "")),
            correspondent=str(data.get("correspondent", "")),
            date=data.get("date"),
            summary=str(data.get("summary", "")),
        )

    def _fallback_title(self, text: str) -> str:
        """Generate a basic title from the first meaningful line of text."""
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if lines:
            title = lines[0][:100]
            return title
        return "Untitled Document"
