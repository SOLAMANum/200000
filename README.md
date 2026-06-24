# Product Catalog — Backend

A high-performance product catalog API for 200,000 products with **stable cursor-based (keyset) pagination**.

## Tech Stack

| Layer | Choice |
|-------|--------|
| Language | Python 3.12 |
| Framework | FastAPI + asyncpg |
| Database | PostgreSQL 16 |

---

## Quick Start

### 1. Clone & configure

```bash
cp .env.example .env   # defaults work out of the box
```

### 2. Start PostgreSQL
Ensure your PostgreSQL database service is running and configured according to the `.env` settings. You will need to create the table structure first by running the commands in `backend/schema.sql` on your database.

### 3. Seed the database
Run the seeding script locally:
```bash
python backend/seed.py
```

This inserts 200,000 rows using a single `INSERT … SELECT generate_series(…)` — entirely server-side, no Python loop. Typical runtime: **2–5 seconds**.

### 4. Open the API docs

```
http://localhost:8000/docs
```

### 5. Open the frontend (optional)

Open `frontend/index.html` in your browser (no build step needed).

---

## API Reference

### `GET /api/products`

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 20 | Items per page (1–100) |
| `cursor` | string | — | Opaque cursor from previous response |
| `category` | string | — | Filter by category |

**Example — first page:**
```
GET /api/products?limit=20
```

**Example — next page:**
```
GET /api/products?limit=20&cursor=eyJ0cyI6IjIwMjUtMDEt...
```

**Response:**
```json
{
  "data": [
    {
      "id": 198432,
      "name": "Electronics Item #198432",
      "category": "Electronics",
      "price": 349.99,
      "created_at": "2025-08-12T14:23:01.123Z",
      "updated_at": "2026-01-05T09:10:22.456Z"
    }
  ],
  "pagination": {
    "next_cursor": "eyJ0cyI6IjIwMjUtMDEtMTVUMTA6M...",
    "has_more": true,
    "limit": 20
  }
}
```

### `GET /api/categories`

Returns all categories with product counts.

```json
[
  { "category": "Automotive",    "count": 20000 },
  { "category": "Beauty",        "count": 20000 },
  ...
]
```

### `GET /api/health`

```json
{ "status": "ok" }
```

---

## Why Keyset Pagination?

### The problem with OFFSET

```sql
-- OFFSET pagination — broken under mutations
SELECT * FROM products ORDER BY created_at DESC LIMIT 20 OFFSET 40;
```

If a new product is inserted while the user is on page 2, the entire result set shifts by one row. Page 3 will either **repeat** the last item of page 2 or **skip** a product entirely.

OFFSET also degrades to **O(n)** — the database must scan and discard all `n` previous rows on every request.

### The keyset solution

The cursor encodes the `(created_at, id)` of the last row returned:

```sql
-- Page N+1 — cursor points at last row of page N
SELECT * FROM products
WHERE (created_at, id) < ($cursor_ts, $cursor_id)
ORDER BY created_at DESC, id DESC
LIMIT 20;
```

With the composite index `(created_at DESC, id DESC)` this is a **single B-tree seek** — **O(log n)** for any page depth.

### Stability guarantee

| Event | Effect on browsing user |
|-------|------------------------|
| New product inserted | Gets `created_at = NOW()` — lands before the cursor. Invisible to users on page 2+. ✓ |
| Product updated | `updated_at` changes but `created_at` does not. Sort order unchanged. ✓ |
| Product deleted | Cursor just skips the gap cleanly. ✓ |

A user browsing pages 2, 3, 4 … is **mathematically guaranteed** never to see a duplicate or miss a row, regardless of concurrent writes.

---

## Database Indexes

```sql
-- All-products query (no category filter)
CREATE INDEX idx_products_created_at_id
    ON products (created_at DESC, id DESC);

-- Category-filtered query
CREATE INDEX idx_products_category_created_at_id
    ON products (category, created_at DESC, id DESC);
```

You can verify the planner uses an index scan:

```sql
EXPLAIN ANALYZE
  SELECT * FROM products
  WHERE (created_at, id) < ('2025-06-01', 99999)
  ORDER BY created_at DESC, id DESC
  LIMIT 20;
-- → Index Scan Backward on idx_products_created_at_id
```

---

## Seed Script

`backend/seed.py` generates 200,000 products in a single SQL statement:

```sql
INSERT INTO products (name, category, price, created_at, updated_at)
SELECT
    category || ' Item #' || i,
    category,
    round((random() * 998 + 1)::numeric, 2),
    NOW() - (random() * INTERVAL '730 days'),
    NOW() - (random() * INTERVAL '30 days')
FROM generate_series(1, 200000) AS i,
     (SELECT ARRAY['Electronics','Clothing',...] AS cat_array) AS cats;
```

No Python loop. No network overhead per row. The DB does all the work.

---

## Project Structure

```
task-pro/
├── backend/
│   ├── main.py            # FastAPI app, CORS, lifespan
│   ├── database.py        # asyncpg pool management
│   ├── routers/
│   │   └── products.py    # /products and /categories endpoints
│   ├── seed.py            # One-shot seed script
│   ├── schema.sql         # DDL + indexes (database setup)
│   └── requirements.txt
├── frontend/
│   ├── index.html         # Single-page UI
│   ├── style.css          # Dark-mode design system
│   └── app.js             # Cursor-stack pagination, fetch, render
├── .env.example
└── README.md
```
