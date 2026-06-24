"""
api/index.py — Vercel serverless entry point.

Vercel's filesystem is read-only except for /tmp.
We copy catalog.db to /tmp/catalog.db on cold start so aiosqlite can
open it (it needs write access for WAL mode PRAGMAs).
"""
import sys
import os
import shutil

# ── resolve paths ──────────────────────────────────────────────────────────────
_root = os.path.join(os.path.dirname(__file__), "..")
_backend = os.path.join(_root, "backend")

# Add backend to path so `from database import ...` works
sys.path.insert(0, _backend)

# ── copy DB to /tmp so SQLite can open in WAL mode ────────────────────────────
_src_db  = os.path.join(_root, "catalog.db")
_tmp_db  = "/tmp/catalog.db"

if os.path.exists(_src_db) and not os.path.exists(_tmp_db):
    shutil.copy2(_src_db, _tmp_db)

# Tell the app to use the writable copy
os.environ.setdefault("DATABASE_URL", _tmp_db)

# ── import app (must happen after env is set) ──────────────────────────────────
from main import app  # noqa: F401  — Vercel picks up `app`
