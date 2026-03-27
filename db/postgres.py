"""Asyncpg connection pool and schema management for PostgreSQL."""

import logging
from pathlib import Path

import asyncpg

from config.settings import settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"


async def create_pool() -> asyncpg.Pool:
    """Create and return the asyncpg connection pool."""
    global _pool
    if _pool is not None:
        return _pool

    try:
        _pool = await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=2,
            max_size=10,
        )
        logger.info("PostgreSQL connection pool created successfully")
        return _pool
    except Exception as e:
        logger.error(f"Failed to create PostgreSQL pool: {e}")
        raise


async def get_pool() -> asyncpg.Pool:
    """Return the existing pool or create a new one (for dependency injection)."""
    if _pool is None:
        return await create_pool()
    return _pool


async def apply_schema() -> None:
    """Read sql/schema.sql and execute it against the database."""
    pool = await get_pool()
    try:
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        async with pool.acquire() as conn:
            await conn.execute(schema_sql)
        logger.info("PostgreSQL schema applied successfully")
    except FileNotFoundError:
        logger.error(f"Schema file not found at {SCHEMA_PATH}")
        raise
    except Exception as e:
        logger.error(f"Failed to apply PostgreSQL schema: {e}")
        raise


async def health_check() -> str:
    """Return 'ok' if PostgreSQL is reachable, otherwise the error message."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            result = await conn.fetchval("SELECT 1")
            if result == 1:
                return "ok"
            return f"Unexpected health check result: {result}"
    except Exception as e:
        return f"PostgreSQL error: {e}"


async def close_pool() -> None:
    """Gracefully close the connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("PostgreSQL connection pool closed")
