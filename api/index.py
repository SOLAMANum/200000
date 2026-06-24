"""
api/index.py — Vercel serverless entry point.

Vercel's filesystem is read-only except /tmp. We copy catalog.db there
on cold start so aiosqlite can open it (WAL mode needs write access).
"""
import sys
import os
import shutil

_root    = os.path.join(os.path.dirname(__file__), "..")
_backend = os.path.join(_root, "backend")

sys.path.insert(0, _backend)

_src_db = os.path.join(_root, "catalog.db")
_tmp_db = "/tmp/catalog.db"

if os.path.exists(_src_db) and not os.path.exists(_tmp_db):
    shutil.copy2(_src_db, _tmp_db)

os.environ.setdefault("DATABASE_URL", _tmp_db)

from main import app  # noqa: F401  — Vercel picks up `app`
