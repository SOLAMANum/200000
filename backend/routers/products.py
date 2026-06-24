"""
routers/products.py — /products and /categories endpoints.

Pagination strategy: Keyset (cursor-based) pagination on (created_at DESC, id DESC).

Why NOT offset pagination
─────────────────────────
OFFSET n forces the database to scan and discard n rows on every request,
making deep pages O(n).  Worse, if a row is inserted or deleted between
requests the "window" shifts, causing duplicates or skipped rows.

How keyset pagination works
────────────────────────────
Instead of "skip N rows", the client remembers the last row it saw and sends
back a cursor encoding (created_at, id) of that row.  The next query becomes:

    WHERE (created_at, id) < (cursor_ts, cursor_id)
    ORDER BY created_at DESC, id DESC
    LIMIT n

PostgreSQL can satisfy this with a single B-tree seek into the composite index
idx_products_created_at_id (or idx_products_category_created_at_id for
filtered queries), making every page O(log n) regardless of depth.

Stability guarantee
────────────────────
New products always have a newer created_at than any cursor that already
exists on a client's browser.  They appear at the top of page 1 and are
invisible to anyone browsing pages 2+.  Updated products change updated_at
but NOT created_at, so the sort order and cursor window are unaffected.
Neither inserts nor updates can cause a client to see a product twice or
skip one.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from database import get_pool

router = APIRouter()

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class Product(BaseModel):
    id: int
    name: str
    category: str
    price: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class Pagination(BaseModel):
    next_cursor: str | None
    has_more: bool
    limit: int


class ProductsResponse(BaseModel):
    data: list[Product]
    pagination: Pagination


class CategoryCount(BaseModel):
    category: str
    count: int


# ---------------------------------------------------------------------------
# Cursor helpers
# ---------------------------------------------------------------------------

def _encode_cursor(created_at: datetime, row_id: int) -> str:
    """Encode (created_at, id) into a URL-safe opaque cursor string."""
    payload = {
        "ts": created_at.isoformat(),
        "id": row_id,
    }
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, int]:
    """Decode a cursor string back to (created_at, id).  Raises 400 on bad input."""
    try:
        raw = base64.urlsafe_b64decode(cursor.encode())
        payload = json.loads(raw)
        ts = datetime.fromisoformat(payload["ts"])
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts, int(payload["id"])
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid cursor: {exc}") from exc


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/products", response_model=ProductsResponse)
async def list_products(
    limit: int = Query(default=20, ge=1, le=100, description="Items per page"),
    cursor: str | None = Query(default=None, description="Opaque pagination cursor"),
    category: str | None = Query(default=None, description="Filter by category"),
    pool=Depends(get_pool),
) -> Any:
    """
    Return a page of products ordered newest-first.

    Pass the `next_cursor` from one response as the `cursor` param of the
    next request to advance through pages.  Results are stable: inserting or
    updating products while browsing will never cause duplicates or skipped rows.
    """
    async with pool.acquire() as conn:
        # We fetch limit+1 rows so we can tell whether there is a next page
        # without a separate COUNT query (which would be expensive on 200k rows).
        fetch_limit = limit + 1
        args: list[Any] = []

        if category and cursor:
            # Filtered + paginated
            cursor_ts, cursor_id = _decode_cursor(cursor)
            args = [category, cursor_ts.isoformat(), cursor_id, fetch_limit]
            sql = """
                SELECT id, name, category, price, created_at, updated_at
                FROM products
                WHERE category = ?
                  AND (created_at, id) < (?, ?)
                ORDER BY created_at DESC, id DESC
                LIMIT ?
            """

        elif category:
            # Filtered, first page
            args = [category, fetch_limit]
            sql = """
                SELECT id, name, category, price, created_at, updated_at
                FROM products
                WHERE category = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
            """

        elif cursor:
            # No filter, paginated
            cursor_ts, cursor_id = _decode_cursor(cursor)
            args = [cursor_ts.isoformat(), cursor_id, fetch_limit]
            sql = """
                SELECT id, name, category, price, created_at, updated_at
                FROM products
                WHERE (created_at, id) < (?, ?)
                ORDER BY created_at DESC, id DESC
                LIMIT ?
            """

        else:
            # No filter, first page
            args = [fetch_limit]
            sql = """
                SELECT id, name, category, price, created_at, updated_at
                FROM products
                ORDER BY created_at DESC, id DESC
                LIMIT ?
            """

        rows = await conn.execute_fetchall(sql, args)

    has_more = len(rows) == fetch_limit
    page_rows = rows[:limit]  # drop the sentinel row if present

    next_cursor: str | None = None
    if has_more and page_rows:
        last = page_rows[-1]
        # In SQLite created_at might be returned as a string, parse it if needed
        last_dt = datetime.fromisoformat(last["created_at"]) if isinstance(last["created_at"], str) else last["created_at"]
        next_cursor = _encode_cursor(last_dt, last["id"])

    return {
        "data": [dict(r) for r in page_rows],
        "pagination": {
            "next_cursor": next_cursor,
            "has_more": has_more,
            "limit": limit,
        },
    }


@router.get("/categories", response_model=list[CategoryCount])
async def list_categories(pool=Depends(get_pool)) -> Any:
    """Return all categories with their product counts, sorted alphabetically."""
    async with pool.acquire() as conn:
        rows = await conn.execute_fetchall(
            """
            SELECT category, COUNT(*) AS count
            FROM products
            GROUP BY category
            ORDER BY category
            """
        )
    return [{"category": r["category"], "count": r["count"]} for r in rows]
