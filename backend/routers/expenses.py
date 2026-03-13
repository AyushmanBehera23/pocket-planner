"""
/api/expenses — CRUD and analytics endpoints for expense records.
"""

import logging
from fastapi import APIRouter, HTTPException
from models.schemas import ExpenseListResponse
from services.database import db_service

logger = logging.getLogger(__name__)
router = APIRouter()


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
    """
    Get spending analytics:
    - category_breakdown: {category: total_spent}
    - monthly_breakdown: {YYYY-MM: total_spent}
    - grand_total, total_bills
    """
    return await db_service.get_monthly_summary()


@router.get("/expenses/{expense_id}")
async def get_expense(expense_id: str):
    """Fetch a single expense record by ID."""
    doc = await db_service.expenses.find_by_id(expense_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Expense not found")
    return doc


@router.delete("/expenses/{expense_id}")
async def delete_expense(expense_id: str):
    """Permanently remove an expense record."""
    deleted = await db_service.delete_expense(expense_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Expense not found")
    return {"success": True, "deleted_id": expense_id}
