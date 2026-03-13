"""
/api/extract — Multimodal bill extraction endpoint.
Accepts image/PDF upload → Gemini Vision → validated JSON → persisted to DB.
"""

import os
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from models.schemas import ExtractionResponse
from services.gemini import GeminiService, MockGeminiService
from services.database import db_service

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_MIME_TYPES = {
    "image/jpeg": "image/jpeg",
    "image/jpg": "image/jpeg",
    "image/png": "image/png",
    "application/pdf": "application/pdf",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def get_gemini_service():
    """
    Dependency injection: use real Gemini API if GEMINI_API_KEY is set,
    otherwise fall back to MockGeminiService for demo mode.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if api_key and api_key not in ("your_gemini_api_key_here", "YOUR_KEY"):
        logger.info("Using real Gemini Vision API")
        return GeminiService(api_key=api_key)
    logger.warning("GEMINI_API_KEY not set — running in demo/mock mode")
    return MockGeminiService()


@router.post("/extract", response_model=ExtractionResponse)
async def extract_bill(
    file: UploadFile = File(..., description="JPEG, PNG, or PDF bill/receipt"),
    gemini=Depends(get_gemini_service),
):
    """
    AI-powered bill extraction pipeline:
    1. Validate file type & size
    2. Send to Gemini Vision with structured prompt
    3. Parse + validate JSON schema (Pydantic)
    4. Persist to expense database
    5. Return full expense record
    """
    # ── Validate file type ──────────────────────────────────────────────────
    content_type = (file.content_type or "").lower().split(";")[0].strip()
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{content_type}'. Accepted: JPEG, PNG, PDF.",
        )

    # ── Read & validate size ────────────────────────────────────────────────
    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(file_bytes) > MAX_FILE_SIZE:
        size_mb = len(file_bytes) / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({size_mb:.1f}MB). Maximum is 10MB.",
        )

    logger.info(f"Processing: {file.filename!r} | {len(file_bytes):,} bytes | {content_type}")

    # ── Gemini extraction ───────────────────────────────────────────────────
    mime_type = ALLOWED_MIME_TYPES[content_type]
    bill, error = await gemini.extract_bill(file_bytes, mime_type)

    if error or bill is None:
        logger.error(f"Extraction failed for {file.filename!r}: {error}")
        return ExtractionResponse(success=False, error=error or "Unknown extraction error")

    # ── Persist to database ─────────────────────────────────────────────────
    record = await db_service.save_expense(
        bill=bill,
        file_name=file.filename,
        file_size=len(file_bytes),
    )

    logger.info(f"Saved: {bill.vendor} | ${bill.total} | {bill.category}")
    return ExtractionResponse(success=True, data=record)
