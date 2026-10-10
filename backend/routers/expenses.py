"""
/api/expenses — CRUD + analytics endpoints for expense records.
Adds PATCH /expenses/{id} for the edit modal (F-07 / B-14).
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from models.schemas import ExpenseListResponse, ExtractedBill
from services.database import db_service

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Request body for PATCH ─────────────────────────────────────────────────

class LineItemIn(BaseModel):
    name: str
    price: float

class ExpenseUpdateRequest(BaseModel):
    vendor:   Optional[str]            = None
    date:     Optional[str]            = None
    category: Optional[str]            = None
    total:    Optional[float]          = None
    items:    Optional[List[LineItemIn]] = None
    notes:    Optional[str]            = None


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("/expenses", response_model=ExpenseListResponse)
async def list_expenses():
    """Fetch all expense records, sorted newest-first."""
    records = await db_service.get_all_expenses()
    monthly_total = sum(r.bill.total for r in records)
    return ExpenseListResponse(
        expenses=records,
        total_count=len(records),
        monthly_total=round(monthly_total, 2),
    )


@router.get("/expenses/summary")
async def get_summary():
    """Spending analytics: category_breakdown, monthly_breakdown, grand_total, total_bills."""
    return await db_service.get_monthly_summary()


@router.get("/expenses/{expense_id}")
async def get_expense(expense_id: str):
    """Fetch a single expense record by ID."""
    record = await db_service.get_expense_by_id(expense_id)
    if not record:
        raise HTTPException(status_code=404, detail="Expense not found")
    return record


@router.patch("/expenses/{expense_id}")
async def update_expense(expense_id: str, body: ExpenseUpdateRequest):
    """
    Partial update: only fields provided in the request body are changed.
    Fixes B-14 / F-07 — expense edit modal.
    """
    existing = await db_service.get_expense_by_id(expense_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Expense not found")

    bill_data = existing.bill.model_dump()

    if body.vendor   is not None: bill_data["vendor"]   = body.vendor
    if body.date     is not None: bill_data["date"]     = body.date
    if body.category is not None: bill_data["category"] = body.category
    if body.total    is not None: bill_data["total"]    = body.total
    if body.items    is not None:
        bill_data["items"] = [i.model_dump() for i in body.items]

    try:
        updated_bill = ExtractedBill(**bill_data)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    record = await db_service.update_expense(expense_id, updated_bill)
    if not record:
        raise HTTPException(status_code=500, detail="Update failed")
    return record


@router.delete("/expenses/{expense_id}")
async def delete_expense(expense_id: str):
    """Permanently remove an expense record."""
    deleted = await db_service.delete_expense(expense_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Expense not found")
    return {"success": True, "deleted_id": expense_id}
