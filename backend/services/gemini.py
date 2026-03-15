"""
Gemini Vision Service — Async multimodal bill extraction.

Architecture:
- GeminiService: real Gemini 1.5 Flash API (requires GEMINI_API_KEY)
- MockGeminiService: realistic demo data, no API key needed

The extraction prompt is engineered for zero-ambiguity JSON output.
_parse_and_validate() handles OCR noise: markdown fences, trailing commas,
numeric strings, and fuzzy date formats.
"""

import asyncio
import base64
import json
import re
import logging
import httpx
from typing import Tuple, Optional, List
from models.schemas import ExtractedBill

logger = logging.getLogger(__name__)

GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-1.5-flash:generateContent"
)

def build_extraction_prompt(categories: Optional[List[str]] = None) -> str:
    category_list = ", ".join(categories) if categories else "Food & Dining, Groceries, Transportation, Utilities, Healthcare, Entertainment, Shopping, Travel, Education, Other"
    
    return f"""\
You are a precise bill/receipt data extraction engine.

Analyze this bill or receipt image and extract ALL information into EXACTLY this JSON schema.
Return ONLY valid JSON — no markdown fences, no explanation, no code blocks, no prose.

Required JSON schema:
{{
  "vendor": "string — the business or store name, properly capitalized",
  "date": "string — in ISO8601 format YYYY-MM-DD",
  "items": [
    {{"name": "string — item description", "price": 0.00, "original_price": 0.00}}
  ],
  "total": 0.00,
  "category": "string — MUST be exactly one of: {category_list}",
  "original_total": 0.00,
  "original_currency": "string — e.g. USD, EUR, INR, AED",
  "exchange_rate": 1.00
}}

Extraction rules:
- Extract EVERY individual line item visible on the bill
- All prices must be positive floating-point numbers with 2 decimal places
- total and price MUST represent the converted value in Indian Rupees (INR). If the bill is already in INR, original_price = price and exchange_rate = 1.0. If the bill is in a foreign currency, estimate the exchange_rate to INR, and calculate the INR total as original_total * exchange_rate.
- If date is unclear or missing, use today's date as YYYY-MM-DD
- If vendor name is unclear, use the most prominent text on the bill
- category must match one of the listed options EXACTLY (case-sensitive)

Return ONLY the JSON object. Nothing before it. Nothing after it.\
"""


class GeminiService:
    """Async Gemini 1.5 Flash multimodal extraction."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=45.0)
        return self._client

    async def extract_bill(
        self, file_bytes: bytes, mime_type: str, categories: Optional[List[str]] = None
    ) -> Tuple[Optional[ExtractedBill], Optional[str]]:
        """
        Send image/PDF bytes to Gemini and return a validated ExtractedBill.
        Returns (bill, None) on success or (None, error_message) on failure.
        """
        b64_data = base64.b64encode(file_bytes).decode("utf-8")

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": build_extraction_prompt(categories)},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": b64_data,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.05,   # Near-deterministic for extraction
                "topK": 1,
                "topP": 0.95,
                "maxOutputTokens": 2048,
            },
        }

        try:
            response = await self.client.post(
                f"{GEMINI_API_URL}?key={self.api_key}",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            result = response.json()

            # Navigate the Gemini response structure
            raw_text = (
                result.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )

            if not raw_text:
                return None, "Gemini returned an empty response."

            bill = self._parse_and_validate(raw_text)
            return bill, None

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == 400:
                return None, "Invalid request to Gemini API. File may be corrupted."
            elif status == 403:
                return None, "Invalid Gemini API key. Check your GEMINI_API_KEY."
            elif status == 429:
                return None, "Gemini rate limit hit. Please wait a moment and retry."
            return None, f"Gemini API error {status}: {e.response.text[:200]}"

        except httpx.TimeoutException:
            return None, "Gemini API timed out (45s). Please try again."

        except (KeyError, IndexError, json.JSONDecodeError, ValueError) as e:
            return None, f"Failed to parse Gemini response: {str(e)}"

        except Exception as e:
            logger.exception("Unexpected Gemini extraction error")
            return None, f"Extraction error: {str(e)}"

    def _parse_and_validate(self, raw_text: str) -> ExtractedBill:
        """
        Robustly parse LLM output into a validated ExtractedBill.

        Handles common OCR/LLM noise:
        - Markdown code fences (```json ... ```)
        - Trailing commas before } or ]
        - Numeric values as strings ("12.99" → 12.99)
        - Extra whitespace and Unicode artifacts
        """
        # Step 1: Strip markdown fences
        cleaned = re.sub(r"```(?:json)?\s*", "", raw_text, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```\s*$", "", cleaned).strip()

        # Step 2: Remove trailing commas (common LLM error)
        cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)

        # Step 3: Extract the JSON object
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise ValueError(
                f"No JSON object found in Gemini response. "
                f"First 300 chars: {raw_text[:300]!r}"
            )

        json_str = match.group(0)

        # Step 4: Parse
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON parse error: {e}. Cleaned text: {json_str[:200]!r}")

        # Step 5: Coerce numeric strings → floats
        if "total" in data and isinstance(data["total"], str):
            data["total"] = float(re.sub(r"[^\d.]", "", data["total"]) or "0")

        for item in data.get("items", []):
            if isinstance(item.get("price"), str):
                item["price"] = float(re.sub(r"[^\d.]", "", item["price"]) or "0")

        # Step 6: Pydantic validation (raises on schema violation)
        return ExtractedBill(**data)

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


class MockGeminiService:
    """
    Realistic mock for demo/testing — no API key required.
    Cycles through a set of pre-built bills with a simulated delay.
    """

    _MOCK_BILLS = [
        {
            "vendor": "Whole Foods Market",
            "date": "2025-03-10",
            "items": [
                {"name": "Organic Almond Milk 64oz", "price": 4.99},
                {"name": "Hass Avocados 4-Pack", "price": 5.49},
                {"name": "Country Sourdough Loaf", "price": 6.29},
                {"name": "Fage Greek Yogurt 32oz", "price": 7.99},
                {"name": "Baby Arugula 5oz", "price": 4.49},
            ],
            "total": 29.25,
            "category": "Groceries",
        },
        {
            "vendor": "Chipotle Mexican Grill",
            "date": "2025-03-11",
            "items": [
                {"name": "Burrito Bowl — Chicken", "price": 12.50},
                {"name": "Chips & Fresh Guacamole", "price": 4.85},
                {"name": "Fountain Beverage Large", "price": 3.10},
            ],
            "total": 20.45,
            "category": "Food & Dining",
        },
        {
            "vendor": "Shell Gas Station",
            "date": "2025-03-12",
            "items": [
                {"name": "Premium Unleaded 87 — 11.2 gal", "price": 45.76},
                {"name": "Monster Energy Drink 16oz", "price": 3.99},
            ],
            "total": 49.75,
            "category": "Transportation",
        },
        {
            "vendor": "CVS Pharmacy",
            "date": "2025-03-09",
            "items": [
                {"name": "Advil Ibuprofen 200ct", "price": 14.99},
                {"name": "Vitamin D3 2000IU", "price": 9.99},
                {"name": "Bandage Variety Pack", "price": 5.49},
            ],
            "total": 30.47,
            "category": "Healthcare",
        },
    ]

    _idx: int = 0

    async def extract_bill(
        self, file_bytes: bytes, mime_type: str, categories: Optional[List[str]] = None
    ) -> Tuple[Optional[ExtractedBill], Optional[str]]:
        await asyncio.sleep(1.8)  # Simulate Gemini processing latency
        bill_data = self._MOCK_BILLS[MockGeminiService._idx % len(self._MOCK_BILLS)]
        MockGeminiService._idx += 1
        return ExtractedBill(**bill_data), None

    async def close(self):
        pass
