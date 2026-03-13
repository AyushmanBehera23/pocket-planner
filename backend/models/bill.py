"""
Pydantic models for bill data validation and MongoDB-style persistence
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import datetime
import uuid


class LineItem(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    price: float = Field(..., ge=0)

    @validator("price")
    def round_price(cls, v):
        return round(v, 2)


class BillExtraction(BaseModel):
    """Schema enforced on Gemini output"""
    vendor: str = Field(..., min_length=1, max_length=200)
    date: str = Field(..., description="ISO8601 date string")
    items: List[LineItem] = Field(..., min_items=1)
    total: float = Field(..., ge=0)
    category: str = Field(..., min_length=1, max_length=100)

    @validator("date")
    def validate_date(cls, v):
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            # Attempt to parse common formats
            for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%B %d, %Y"]:
                try:
                    parsed = datetime.strptime(v, fmt)
                    return parsed.strftime("%Y-%m-%d")
                except ValueError:
                    continue
            raise ValueError(f"Cannot parse date: {v}")
        return v

    @validator("total")
    def round_total(cls, v):
        return round(v, 2)


class BillRecord(BaseModel):
    """MongoDB-style document with metadata"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    extraction: BillExtraction
    created_at: datetime = Field(default_factory=datetime.utcnow)
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0, le=1.0)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class ExtractionResponse(BaseModel):
    success: bool
    bill: Optional[BillRecord] = None
    error: Optional[str] = None
    raw_response: Optional[str] = None
