"""
Mock NoSQL (MongoDB-style) database service.
Uses in-memory storage with document structure.
Replace with Motor (async pymongo) for production.
"""

import uuid
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from collections import defaultdict

from models.schemas import ExpenseRecord, ExtractedBill

logger = logging.getLogger(__name__)


class MockCollection:
    """Simulates a MongoDB collection with async interface."""

    def __init__(self, name: str):
        self.name = name
        self._documents: Dict[str, Dict[str, Any]] = {}

    async def insert_one(self, document: dict) -> str:
        doc_id = str(uuid.uuid4())
        document["_id"] = doc_id
        self._documents[doc_id] = document
        return doc_id

    async def find_all(self) -> List[dict]:
        return sorted(
            list(self._documents.values()),
            key=lambda d: d.get("created_at", ""),
            reverse=True,
        )

    async def find_by_id(self, doc_id: str) -> Optional[dict]:
        return self._documents.get(doc_id)

    async def delete_one(self, doc_id: str) -> bool:
        if doc_id in self._documents:
            del self._documents[doc_id]
            return True
        return False

    async def count(self) -> int:
        return len(self._documents)


class DatabaseService:
    """Top-level DB service — mimics MongoClient pattern."""

    def __init__(self):
        self.expenses: MockCollection = MockCollection("expenses")
        self._initialized = False

    async def initialize(self):
        """Seed with sample data for demo."""
        if self._initialized:
            return
        self._initialized = True
        logger.info("Database initialized with mock data")

        seeds = [
            ExtractedBill(
                vendor="Amazon",
                date="2024-01-10",
                items=[
                    {"name": "USB-C Hub 7-in-1", "price": 29.99},
                    {"name": "Mechanical Keyboard", "price": 89.00},
                ],
                total=118.99,
                category="Shopping",
            ),
            ExtractedBill(
                vendor="Spotify",
                date="2024-01-01",
                items=[{"name": "Premium Monthly Subscription", "price": 10.99}],
                total=10.99,
                category="Entertainment",
            ),
            ExtractedBill(
                vendor="Trader Joe's",
                date="2024-01-12",
                items=[
                    {"name": "Mandarin Chicken", "price": 4.99},
                    {"name": "Everything Bagels", "price": 3.49},
                    {"name": "Cold Brew Coffee", "price": 6.99},
                    {"name": "Cheese Crisps", "price": 2.99},
                ],
                total=18.46,
                category="Groceries",
            ),
            ExtractedBill(
                vendor="Uber",
                date="2024-01-14",
                items=[
                    {"name": "Trip to Airport", "price": 34.20},
                    {"name": "Tip", "price": 5.00},
                ],
                total=39.20,
                category="Transportation",
            ),
        ]

        for bill in seeds:
            await self.save_expense(bill, file_name="seed_data.json")

    async def save_expense(
        self,
        bill: ExtractedBill,
        file_name: Optional[str] = None,
        file_size: Optional[int] = None,
    ) -> ExpenseRecord:
        doc = {
            "bill": bill.model_dump(),
            "created_at": datetime.now().isoformat(),
            "file_name": file_name,
            "file_size": file_size,
        }
        doc_id = await self.expenses.insert_one(doc)
        doc["id"] = doc_id
        return ExpenseRecord(**doc)

    async def get_all_expenses(self) -> List[ExpenseRecord]:
        docs = await self.expenses.find_all()
        records = []
        for doc in docs:
            try:
                records.append(
                    ExpenseRecord(
                        id=doc["_id"],
                        bill=ExtractedBill(**doc["bill"]),
                        created_at=doc.get("created_at"),
                        file_name=doc.get("file_name"),
                        file_size=doc.get("file_size"),
                    )
                )
            except Exception as e:
                logger.warning(f"Skipping malformed record {doc.get('_id')}: {e}")
        return records

    async def delete_expense(self, expense_id: str) -> bool:
        return await self.expenses.delete_one(expense_id)

    async def get_monthly_summary(self) -> Dict[str, Any]:
        records = await self.get_all_expenses()
        category_totals = defaultdict(float)
        monthly_totals = defaultdict(float)

        for record in records:
            bill = record.bill
            category_totals[bill.category] += bill.total
            month_key = bill.date[:7] if bill.date else "unknown"
            monthly_totals[month_key] += bill.total

        return {
            "category_breakdown": dict(category_totals),
            "monthly_breakdown": dict(monthly_totals),
            "grand_total": sum(category_totals.values()),
            "total_bills": len(records),
        }

    async def close(self):
        logger.info("Database connection closed")


# Singleton instance
db_service = DatabaseService()
