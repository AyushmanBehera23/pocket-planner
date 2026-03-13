"""
Mock MongoDB-style in-memory database with persistence simulation
In production: replace with motor (async MongoDB driver)
"""

from typing import Dict, List, Optional
from datetime import datetime


class MockCollection:
    """Simulates a MongoDB collection with async interface"""

    def __init__(self, name: str):
        self.name = name
        self._documents: Dict[str, dict] = {}

    async def insert_one(self, document: dict) -> str:
        doc_id = document.get("id", str(len(self._documents)))
        self._documents[doc_id] = {**document, "_id": doc_id}
        return doc_id

    async def find_one(self, query: dict) -> Optional[dict]:
        for doc in self._documents.values():
            if all(doc.get(k) == v for k, v in query.items()):
                return doc
        return None

    async def find_all(self, query: dict = None, sort_by: str = "created_at", limit: int = 100) -> List[dict]:
        docs = list(self._documents.values())
        if query:
            docs = [d for d in docs if all(d.get(k) == v for k, v in query.items())]
        docs.sort(key=lambda x: x.get(sort_by, ""), reverse=True)
        return docs[:limit]

    async def delete_one(self, doc_id: str) -> bool:
        if doc_id in self._documents:
            del self._documents[doc_id]
            return True
        return False

    async def count(self) -> int:
        return len(self._documents)


class MockDatabase:
    def __init__(self):
        self.bills = MockCollection("bills")


_db: Optional[MockDatabase] = None


async def init_db():
    global _db
    _db = MockDatabase()
    await _seed_sample_data(_db)


async def get_db() -> MockDatabase:
    if _db is None:
        await init_db()
    return _db


async def _seed_sample_data(db: MockDatabase):
    """Seed realistic sample expense data"""
    from models.bill import BillRecord, BillExtraction, LineItem

    samples = [
        {
            "vendor": "Whole Foods Market",
            "date": "2025-03-01",
            "items": [{"name": "Organic Apples", "price": 4.99}, {"name": "Greek Yogurt", "price": 3.49}, {"name": "Almond Milk", "price": 5.29}],
            "total": 13.77,
            "category": "Groceries",
        },
        {
            "vendor": "Shell Gas Station",
            "date": "2025-03-03",
            "items": [{"name": "Regular Unleaded (12.4 gal)", "price": 47.12}],
            "total": 47.12,
            "category": "Transportation",
        },
        {
            "vendor": "Netflix",
            "date": "2025-03-05",
            "items": [{"name": "Standard Plan - Monthly", "price": 15.49}],
            "total": 15.49,
            "category": "Entertainment",
        },
        {
            "vendor": "Chipotle Mexican Grill",
            "date": "2025-03-07",
            "items": [{"name": "Burrito Bowl", "price": 10.75}, {"name": "Chips & Guac", "price": 4.25}, {"name": "Large Drink", "price": 3.00}],
            "total": 18.00,
            "category": "Dining",
        },
        {
            "vendor": "CVS Pharmacy",
            "date": "2025-03-09",
            "items": [{"name": "Advil 200ct", "price": 12.99}, {"name": "Bandages", "price": 5.49}],
            "total": 18.48,
            "category": "Healthcare",
        },
        {
            "vendor": "Amazon",
            "date": "2025-03-11",
            "items": [{"name": "USB-C Hub", "price": 34.99}, {"name": "Phone Case", "price": 14.99}],
            "total": 49.98,
            "category": "Shopping",
        },
        {
            "vendor": "Starbucks",
            "date": "2025-03-12",
            "items": [{"name": "Venti Latte", "price": 6.45}, {"name": "Blueberry Muffin", "price": 3.95}],
            "total": 10.40,
            "category": "Dining",
        },
    ]

    for s in samples:
        items = [LineItem(**i) for i in s["items"]]
        extraction = BillExtraction(
            vendor=s["vendor"],
            date=s["date"],
            items=items,
            total=s["total"],
            category=s["category"],
        )
        record = BillRecord(extraction=extraction, file_name="sample.jpg", file_type="image/jpeg")
        await db.bills.insert_one(record.dict())
