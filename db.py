from __future__ import annotations

import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
_pool: asyncpg.Pool | None = None


def _ensure_database_url() -> None:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL must be set in environment variables")


async def connect_db() -> None:
    global _pool
    _ensure_database_url()
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
        await init_db()


async def disconnect_db() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database is not connected")
    return _pool


async def init_db() -> None:
    global _pool
    if _pool is None:
        raise RuntimeError("Database pool is not initialized")

    schema_path = Path(__file__).with_name("schema.sql")
    if not schema_path.exists():
        raise RuntimeError(f"Schema file not found: {schema_path}")

    sql = schema_path.read_text()
    async with _pool.acquire() as conn:
        await conn.execute(sql)


async def fetchrow(query: str, *args) -> asyncpg.Record | None:
    if _pool is None:
        raise RuntimeError("Database is not connected")
    async with _pool.acquire() as conn:
        return await conn.fetchrow(query, *args)


async def fetch(query: str, *args) -> list[asyncpg.Record]:
    if _pool is None:
        raise RuntimeError("Database is not connected")
    async with _pool.acquire() as conn:
        return await conn.fetch(query, *args)


async def execute(query: str, *args) -> str:
    if _pool is None:
        raise RuntimeError("Database is not connected")
    async with _pool.acquire() as conn:
        return await conn.execute(query, *args)


async def executemany(query: str, args_list: list[tuple]) -> None:
    if _pool is None:
        raise RuntimeError("Database is not connected")
    async with _pool.acquire() as conn:
        await conn.executemany(query, args_list)
