"""
Gemini Vision Service — Async multimodal bill extraction.

Fixes:
  B-06: PDF is now converted to PNG via PyMuPDF before being sent to Gemini,
        because Gemini's inline_data API does not support PDF natively.

Architecture:
  - GeminiService: real Gemini 1.5 Flash API (requires GEMINI_API_KEY)
  - MockGeminiService: realistic demo data, no API key needed
"""

import asyncio
import base64
import io
import json
import os
import re
import logging
import httpx
from typing import Tuple, Optional, List
from models.schemas import ExtractedBill

logger = logging.getLogger(__name__)

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
GEMINI_API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
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
- total and price MUST represent the value in Indian Rupees (INR, ₹). If the bill is already in INR (₹), extract the values as shown, set original_price = price, original_currency = "INR", and exchange_rate = 1.0. If the bill is in a foreign currency (e.g. USD, EUR), convert total and line prices to INR, estimate the exchange_rate to INR, and set original_total / original_currency accordingly.
- If date is unclear or missing, use today's date as YYYY-MM-DD
- If vendor name is unclear, use the most prominent text on the bill
- category must match one of the listed options EXACTLY (case-sensitive)

Return ONLY the JSON object. Nothing before it. Nothing after it.\
"""


def _pdf_to_png_bytes(pdf_bytes: bytes) -> bytes:
    """
    Convert the first page of a PDF to PNG bytes using PyMuPDF (fitz).
    This lets us pass PDFs to Gemini as image/png (B-06 fix).
    """
    import fitz  # PyMuPDF

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    if len(doc) == 0:
        raise ValueError("PDF contains no pages.")
    page = doc[0]
    # 200 DPI gives good quality without exceeding Gemini's size limits
    mat = fitz.Matrix(200 / 72, 200 / 72)
    pix = page.get_pixmap(matrix=mat)
    return pix.tobytes("png")


class GeminiService:
    """Async Gemini 1.5 Flash multimodal extraction."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def extract_bill(
        self, file_bytes: bytes, mime_type: str, categories: Optional[List[str]] = None
    ) -> Tuple[Optional[ExtractedBill], Optional[str]]:
        """
        Send image/PDF bytes to Gemini and return a validated ExtractedBill.
        PDFs are first converted to PNG (B-06).
        Returns (bill, None) on success or (None, error_message) on failure.
        """
        # ── B-06: Convert PDF → PNG ───────────────────────────────────────
        if mime_type == "application/pdf":
            try:
                file_bytes = _pdf_to_png_bytes(file_bytes)
                mime_type = "image/png"
                logger.info("PDF converted to PNG for Gemini extraction.")
            except Exception as e:
                return None, f"Failed to convert PDF to image: {e}"

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
                "temperature": 0.05,
                "topK": 1,
                "topP": 0.95,
                "maxOutputTokens": 4096,
                "response_mime_type": "application/json",
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

            raw_text = (
                result.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )

            if not raw_text:
                logger.error(f"Gemini empty response. Full result: {result}")
                return None, "Gemini returned an empty response."

            logger.info(f"Gemini raw response (first 500 chars): {raw_text[:500]!r}")
            try:
                bill = self._parse_and_validate(raw_text)
            except Exception as parse_err:
                logger.error(f"Parse failed. Raw text: {raw_text[:1000]!r}")
                return None, f"Failed to parse Gemini response: {parse_err}"
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
            return None, "Gemini API timed out (60s). Please try again."

        except (KeyError, IndexError, json.JSONDecodeError, ValueError) as e:
            return None, f"Failed to parse Gemini response: {str(e)}"

        except Exception as e:
            logger.exception("Unexpected Gemini extraction error")
            return None, f"Extraction error: {str(e)}"

    def _parse_and_validate(self, raw_text: str) -> ExtractedBill:
        """
        Robustly parse LLM output into a validated ExtractedBill.
        Handles markdown fences, trailing commas, numeric strings.
        """
        cleaned = re.sub(r"```(?:json)?\s*", "", raw_text, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```\s*$", "", cleaned).strip()
        cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)

        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise ValueError(
                f"No JSON object found in Gemini response. "
                f"First 300 chars: {raw_text[:300]!r}"
            )

        json_str = match.group(0)

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON parse error: {e}. Cleaned text: {json_str[:200]!r}")

        if "total" in data and isinstance(data["total"], str):
            data["total"] = float(re.sub(r"[^\d.]", "", data["total"]) or "0")

        for item in data.get("items", []):
            if isinstance(item.get("price"), str):
                item["price"] = float(re.sub(r"[^\d.]", "", item["price"]) or "0")

        return ExtractedBill(**data)

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


class MockGeminiService:
    """
    Realistic mock for demo/testing — no API key required.
    Cycles through pre-built bills with a simulated delay.
    """

    _MOCK_BILLS = [
        {
            "vendor": "Blinkit",
            "date": "2025-03-10",
            "items": [
                {"name": "Amul Taaza Toned Milk 1L", "price": 54.00, "original_price": 54.00},
                {"name": "Hass Avocados (Pack of 2)", "price": 230.00, "original_price": 230.00},
                {"name": "Aashirvaad Atta 5kg", "price": 275.00, "original_price": 275.00},
                {"name": "Epigamia Greek Yogurt 90g", "price": 95.00, "original_price": 95.00},
            ],
            "total": 654.00,
            "category": "Groceries",
            "original_total": 654.00,
            "original_currency": "INR",
            "exchange_rate": 1.0,
        },
        {
            "vendor": "Swiggy",
            "date": "2025-03-11",
            "items": [
                {"name": "Chicken Dum Biryani (Regular)", "price": 360.00, "original_price": 360.00},
                {"name": "Garlic Naan (2 pcs)", "price": 110.00, "original_price": 110.00},
                {"name": "Gulab Jamun (2 pcs)", "price": 80.00, "original_price": 80.00},
            ],
            "total": 550.00,
            "category": "Food & Dining",
            "original_total": 550.00,
            "original_currency": "INR",
            "exchange_rate": 1.0,
        },
        {
            "vendor": "Indian Oil Fuel Station",
            "date": "2025-03-12",
            "items": [
                {"name": "Petrol ExtraPremium — 16.5 L", "price": 1750.00, "original_price": 1750.00},
            ],
            "total": 1750.00,
            "category": "Transportation",
            "original_total": 1750.00,
            "original_currency": "INR",
            "exchange_rate": 1.0,
        },
        {
            "vendor": "Apollo Pharmacy",
            "date": "2025-03-09",
            "items": [
                {"name": "Dolo 650mg Tablets (15 pcs)", "price": 35.00, "original_price": 35.00},
                {"name": "Limcee Vitamin C 500mg", "price": 105.00, "original_price": 105.00},
                {"name": "Hansaplast Bandages (Pack of 10)", "price": 50.00, "original_price": 50.00},
            ],
            "total": 190.00,
            "category": "Healthcare",
            "original_total": 190.00,
            "original_currency": "INR",
            "exchange_rate": 1.0,
        },
        {
            "vendor": "Amazon India",
            "date": "2025-03-14",
            "items": [
                {"name": "65W USB-C GaN Fast Charger", "price": 1499.00, "original_price": 1499.00},
                {"name": "Aluminium Laptop Stand", "price": 799.00, "original_price": 799.00},
            ],
            "total": 2298.00,
            "category": "Shopping",
            "original_total": 2298.00,
            "original_currency": "INR",
            "exchange_rate": 1.0,
        },
    ]

    _idx: int = 0

    async def extract_bill(
        self, file_bytes: bytes, mime_type: str, categories: Optional[List[str]] = None
    ) -> Tuple[Optional[ExtractedBill], Optional[str]]:
        await asyncio.sleep(2.0)  # Simulate Gemini processing latency
        bill_data = self._MOCK_BILLS[MockGeminiService._idx % len(self._MOCK_BILLS)]
        MockGeminiService._idx += 1
        return ExtractedBill(**bill_data), None

    async def close(self):
        pass
