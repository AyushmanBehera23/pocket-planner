"""
SQLite-backed DatabaseService — replaces the in-memory MockCollection.
Fixes B-04: data is now persisted across server restarts.

Storage layout:
  expenses table: id, bill_json, created_at, file_name, file_size
"""

import uuid
import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from collections import defaultdict

import aiosqlite

from models.schemas import ExpenseRecord, ExtractedBill

logger = logging.getLogger(__name__)

DB_PATH = "pocket_planner.db"


class DatabaseService:
    """Async SQLite-backed expense store."""

    async def initialize(self) -> None:
        """Create schema and seed sample data if the table is empty."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id          TEXT PRIMARY KEY,
                    bill_json   TEXT NOT NULL,
                    created_at  TEXT NOT NULL,
                    file_name   TEXT,
                    file_size   INTEGER
                )
            """)
            await db.commit()

            async with db.execute("SELECT COUNT(*) FROM expenses") as cur:
                (count,) = await cur.fetchone()

        if count == 0:
            logger.info("Seeding database with sample data…")
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
                ExtractedBill(
                    vendor="Whole Foods Market",
                    date="2024-02-03",
                    items=[
                        {"name": "Organic Almond Milk", "price": 4.99},
                        {"name": "Sourdough Loaf", "price": 6.29},
                        {"name": "Baby Spinach 5oz", "price": 4.49},
                        {"name": "Hass Avocados", "price": 5.49},
                    ],
                    total=21.26,
                    category="Groceries",
                ),
                ExtractedBill(
                    vendor="Shell Gas Station",
                    date="2024-02-08",
                    items=[
                        {"name": "Premium Unleaded 11.2 gal", "price": 45.76},
                        {"name": "Monster Energy Drink", "price": 3.99},
                    ],
                    total=49.75,
                    category="Transportation",
                ),
                ExtractedBill(
                    vendor="Netflix",
                    date="2024-02-01",
                    items=[{"name": "Standard Plan Monthly", "price": 15.49}],
                    total=15.49,
                    category="Entertainment",
                ),
            ]
            for bill in seeds:
                await self.save_expense(bill, file_name="seed_data.json")

        logger.info("Database ready — SQLite @ %s", DB_PATH)

    # ── CRUD ──────────────────────────────────────────────────────────────────

    async def save_expense(
        self,
        bill: ExtractedBill,
        file_name: Optional[str] = None,
        file_size: Optional[int] = None,
    ) -> ExpenseRecord:
        doc_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        bill_json = json.dumps(bill.model_dump())

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO expenses (id, bill_json, created_at, file_name, file_size) "
                "VALUES (?, ?, ?, ?, ?)",
                (doc_id, bill_json, created_at, file_name, file_size),
            )
            await db.commit()

        return ExpenseRecord(
            id=doc_id,
            bill=bill,
            created_at=created_at,
            file_name=file_name,
            file_size=file_size,
        )

    async def get_all_expenses(self) -> List[ExpenseRecord]:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM expenses ORDER BY created_at DESC"
            ) as cur:
                rows = await cur.fetchall()

        records: List[ExpenseRecord] = []
        for row in rows:
            try:
                bill_data = json.loads(row["bill_json"])
                records.append(
                    ExpenseRecord(
                        id=row["id"],
                        bill=ExtractedBill(**bill_data),
                        created_at=row["created_at"],
                        file_name=row["file_name"],
                        file_size=row["file_size"],
                    )
                )
            except Exception as e:
                logger.warning("Skipping malformed record %s: %s", row["id"], e)
        return records

    async def get_expense_by_id(self, expense_id: str) -> Optional[ExpenseRecord]:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM expenses WHERE id = ?", (expense_id,)
            ) as cur:
                row = await cur.fetchone()

        if not row:
            return None
        try:
            return ExpenseRecord(
                id=row["id"],
                bill=ExtractedBill(**json.loads(row["bill_json"])),
                created_at=row["created_at"],
                file_name=row["file_name"],
                file_size=row["file_size"],
            )
        except Exception as e:
            logger.warning("Malformed record %s: %s", expense_id, e)
            return None

    async def update_expense(
        self, expense_id: str, bill: ExtractedBill
    ) -> Optional[ExpenseRecord]:
        """Update the bill data of an existing expense (for edit modal — F-07)."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT created_at, file_name, file_size FROM expenses WHERE id = ?",
                (expense_id,),
            ) as cur:
                row = await cur.fetchone()
            if not row:
                return None
            await db.execute(
                "UPDATE expenses SET bill_json = ? WHERE id = ?",
                (json.dumps(bill.model_dump()), expense_id),
            )
            await db.commit()

        return ExpenseRecord(
            id=expense_id,
            bill=bill,
            created_at=row[0],
            file_name=row[1],
            file_size=row[2],
        )

    async def delete_expense(self, expense_id: str) -> bool:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT id FROM expenses WHERE id = ?", (expense_id,)
            ) as cur:
                exists = await cur.fetchone()
            if not exists:
                return False
            await db.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
            await db.commit()
        return True

    async def get_monthly_summary(self) -> Dict[str, Any]:
        records = await self.get_all_expenses()
        category_totals: Dict[str, float] = defaultdict(float)
        monthly_totals: Dict[str, float] = defaultdict(float)

        for record in records:
            bill = record.bill
            category_totals[bill.category] += bill.total
            month_key = bill.date[:7] if bill.date else "unknown"
            monthly_totals[month_key] += bill.total

        return {
            "category_breakdown": {k: round(v, 2) for k, v in category_totals.items()},
            "monthly_breakdown": dict(sorted(monthly_totals.items())),
            "grand_total": round(sum(category_totals.values()), 2),
            "total_bills": len(records),
        }

    async def count(self) -> int:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM expenses") as cur:
                (n,) = await cur.fetchone()
        return n

    async def close(self) -> None:
        logger.info("Database connection closed")


# Singleton
db_service = DatabaseService()
