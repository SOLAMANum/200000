"""
database.py — aiosqlite connection lifecycle management.

The connection is created once at application startup and shared across all
requests. FastAPI's lifespan context manager handles teardown cleanly.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import aiosqlite
from fastapi import FastAPI

_conn: aiosqlite.Connection | None = None

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI lifespan: create connection on startup, close on shutdown."""
    global _conn

    db_path = os.getenv("DATABASE_URL", "catalog.db")
    if db_path == "catalog.db":
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "catalog.db")

    _conn = await aiosqlite.connect(db_path)
    _conn.row_factory = aiosqlite.Row

    await _conn.execute("PRAGMA journal_mode=WAL")
    await _conn.execute("PRAGMA synchronous=NORMAL")

    yield  

    await _conn.close()
    _conn = None


def get_conn() -> aiosqlite.Connection:
    """Return the active database connection (raises if called before startup)."""
    if _conn is None:
        raise RuntimeError("Database connection is not initialised")
    return _conn

class FakePool:
    def __init__(self, conn):
        self.conn = conn

    @asynccontextmanager
    async def acquire(self):
        yield self.conn

def get_pool():
    """Returns a fake pool that yields the single aiosqlite connection."""
    return FakePool(get_conn())
