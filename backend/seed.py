#!/usr/bin/env python3
"""
seed.py — Populate the products table with 200,000 rows in SQLite.

Strategy: Use executemany with a generator to insert 200,000 rows efficiently.
"""

import asyncio
import os
import time
import random
from datetime import datetime, timedelta, timezone

import aiosqlite

DATABASE_URL = os.getenv("DATABASE_URL", "catalog.db")
if DATABASE_URL.startswith("postgres"):
    DATABASE_URL = "catalog.db"

CATEGORIES = [
    "Electronics",
    "Clothing",
    "Books",
    "Home & Garden",
    "Sports",
    "Toys",
    "Food & Grocery",
    "Beauty",
    "Automotive",
    "Office Supplies",
]

async def main() -> None:
    print(f"Connecting to SQLite database: {DATABASE_URL!r}")
    
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    async with aiosqlite.connect(DATABASE_URL) as conn:
        await conn.executescript(schema_sql)
        await conn.commit()

        async with conn.execute("SELECT COUNT(*) FROM products") as cur:
            row = await cur.fetchone()
            existing = row[0] if row else 0

        if existing > 0:
            print(f"⚠  Table already has {existing:,} rows.")
            answer = input("   Delete all and re-seed? [y/N] ").strip().lower()
            if answer != "y":
                print("Aborted — no changes made.")
                return
            await conn.execute("DELETE FROM products")
            await conn.commit()
            print("   Table cleared.")

        print("Generating 200,000 products for insertion...")
        t0 = time.perf_counter()

        now = datetime.now(timezone.utc)
        
        def generate_data():
            for i in range(1, 200001):
                category = CATEGORIES[(i - 1) % len(CATEGORIES)]
                name = f"{category} Item #{i}"
                price = round(random.uniform(1.0, 999.99), 2)
                
                days_ago = random.uniform(0, 730)
                created_at = now - timedelta(days=days_ago)
                
                updated_days_ago = random.uniform(0, 30)
                updated_at = now - timedelta(days=updated_days_ago)
                
                yield (name, category, price, created_at.isoformat(), updated_at.isoformat())

        print("Seeding 200,000 products (this might take a few seconds)...")
        
        insert_sql = "INSERT INTO products (name, category, price, created_at, updated_at) VALUES (?, ?, ?, ?, ?)"
        
        await conn.executemany(insert_sql, generate_data())
        await conn.commit()

        elapsed = time.perf_counter() - t0
        
        async with conn.execute("SELECT COUNT(*) FROM products") as cur:
            row = await cur.fetchone()
            final_count = row[0] if row else 0
            
        print(f"✓  Inserted {final_count:,} rows in {elapsed:.2f}s")

        print("\nCategory distribution:")
        async with conn.execute("SELECT category, COUNT(*) AS cnt FROM products GROUP BY category ORDER BY cnt DESC") as cur:
            rows = await cur.fetchall()
            for row in rows:
                print(f"  {row[0]:<20} {row[1]:>7,}")

if __name__ == "__main__":
    asyncio.run(main())
