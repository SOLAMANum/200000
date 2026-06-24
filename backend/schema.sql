-- =============================================================================
-- Product Catalog Schema (SQLite)
-- =============================================================================

CREATE TABLE IF NOT EXISTS products (
    id          INTEGER          PRIMARY KEY AUTOINCREMENT,
    name        TEXT             NOT NULL,
    category    TEXT             NOT NULL,
    price       REAL             NOT NULL,
    created_at  TEXT             NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TEXT             NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- Indexes for keyset (cursor-based) pagination
-- ---------------------------------------------------------------------------

-- Global browse: newest-first, no category filter
CREATE INDEX IF NOT EXISTS idx_products_created_at_id
    ON products (created_at DESC, id DESC);

-- Category-filtered browse: category first so the index can narrow the set,
-- then the keyset columns for ordering and cursor seeks.
CREATE INDEX IF NOT EXISTS idx_products_category_created_at_id
    ON products (category, created_at DESC, id DESC);
