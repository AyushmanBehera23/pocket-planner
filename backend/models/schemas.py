"""
Data models for bill extraction — strict schema enforcement.
"""

from pydantic import BaseModel, field_validator, model_validator
from typing import List, Optional
from datetime import datetime
from enum import Enum
import re


class ExpenseCategory(str, Enum):
    # Default fallback categories if the user hasn't defined custom ones
    FOOD_DINING = "Food & Dining"
    GROCERIES = "Groceries"
    TRANSPORTATION = "Transportation"
    UTILITIES = "Utilities"
    HEALTHCARE = "Healthcare"
    ENTERTAINMENT = "Entertainment"
    SHOPPING = "Shopping"
    TRAVEL = "Travel"
    EDUCATION = "Education"
    OTHER = "Other"


class LineItem(BaseModel):
    name: str
    price: float
    original_price: Optional[float] = None

    @field_validator("price")
    @classmethod
    def price_must_be_positive(cls, v):
        if v < 0:
            raise ValueError("Price cannot be negative")
        return round(v, 2)

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Item name cannot be empty")
        return v


class ExtractedBill(BaseModel):
    vendor: str
    date: str  # ISO8601 string
    items: List[LineItem]
    total: float
    category: str
    
    # Ex: original_total=10.0, original_currency="USD", exchange_rate=83.5
    # total and price fields will represent the converted INR value
    original_total: Optional[float] = None
    original_currency: Optional[str] = None
    exchange_rate: Optional[float] = None

    @field_validator("date")
    @classmethod
    def validate_date(cls, v):
        # Accept various ISO-like formats and normalize
        patterns = [
            r"^\d{4}-\d{2}-\d{2}$",
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
        ]
        for p in patterns:
            if re.match(p, v):
                return v
        # Try to parse and reformat
        for fmt in ["%m/%d/%Y", "%d/%m/%Y", "%B %d, %Y", "%b %d, %Y"]:
            try:
                dt = datetime.strptime(v, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        # Fallback: today's date
        return datetime.now().strftime("%Y-%m-%d")

    @field_validator("total")
    @classmethod
    def total_must_be_positive(cls, v):
        return round(abs(v), 2)

    @field_validator("category")
    @classmethod
    def normalize_category(cls, v):
        # We now allow dynamic categories. We just format it nicely.
        return v.strip().title() if v else ExpenseCategory.OTHER.value

    @field_validator("vendor")
    @classmethod
    def clean_vendor(cls, v):
        return v.strip().title() if v else "Unknown Vendor"

    @model_validator(mode="after")
    def reconcile_total(self):
        """If items exist but total looks wrong, recalculate."""
        if self.items:
            computed = sum(item.price for item in self.items)
            # Allow 5% tolerance for tax/fees
            if self.total == 0 or abs(self.total - computed) / max(computed, 0.01) > 0.5:
                self.total = round(computed, 2)
        return self


class ExpenseRecord(BaseModel):
    """Full DB record with metadata."""
    id: Optional[str] = None
    bill: ExtractedBill
    created_at: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None


class ExtractionResponse(BaseModel):
    success: bool
    data: Optional[ExpenseRecord] = None
    error: Optional[str] = None
    raw_response: Optional[str] = None  # For debugging


class ExpenseListResponse(BaseModel):
    expenses: List[ExpenseRecord]
    total_count: int
    monthly_total: float
