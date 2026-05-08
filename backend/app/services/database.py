"""PostgreSQL database service for project history persistence.

Uses asyncpg for async connections to a PostgreSQL database (e.g. Zeabur-managed).
The ``project_history`` table stores per-session snapshots so users can browse,
restore, and delete past generation sessions.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.core.config import get_database_settings

logger = logging.getLogger("database")

# ---------------------------------------------------------------------------
# Connection pool (lazy singleton)
# ---------------------------------------------------------------------------
_pool: Any = None


async def _get_pool() -> Any:
    """Return the shared asyncpg connection pool, creating it on first call."""
    global _pool
    if _pool is not None:
        return _pool

    settings = get_database_settings()
    if not settings.configured:
        return None

    try:
        import asyncpg  # noqa: WPS433 — imported inside function to keep the dep optional

        _pool = await asyncpg.create_pool(settings.url, min_size=1, max_size=5, command_timeout=30)
        return _pool
    except Exception as exc:
        logger.warning("failed to create database pool: %s", exc)
        return None


async def close_pool() -> None:
    """Gracefully close the connection pool (call on app shutdown)."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS project_history (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL DEFAULT 'legacy-shared-user',
    user_snapshot_json TEXT NOT NULL DEFAULT '{}',
    product_name TEXT NOT NULL DEFAULT '',
    category     TEXT NOT NULL DEFAULT '',
    style_id     TEXT NOT NULL DEFAULT '',
    style_name   TEXT NOT NULL DEFAULT '',
    platform_id  TEXT NOT NULL DEFAULT 'tmall',
    thumbnail    TEXT DEFAULT '',
    image_count  INTEGER DEFAULT 0,
    state_json   TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

_CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_history_created ON project_history (created_at DESC);
"""

_ALTER_TABLE_SQL = """
ALTER TABLE project_history
    ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'legacy-shared-user',
    ADD COLUMN IF NOT EXISTS user_snapshot_json TEXT NOT NULL DEFAULT '{}';
"""

_CREATE_USER_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_history_user_created ON project_history (user_id, created_at DESC);
"""


async def ensure_tables() -> None:
    """Create the ``project_history`` table if it does not already exist."""
    pool = await _get_pool()
    if pool is None:
        logger.info("database not configured — skipping table creation")
        return

    async with pool.acquire() as conn:
        await conn.execute(_CREATE_TABLE_SQL)
        await conn.execute(_ALTER_TABLE_SQL)
        await conn.execute(_CREATE_INDEX_SQL)
        await conn.execute(_CREATE_USER_INDEX_SQL)
    logger.info("project_history table ensured")


# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------

async def list_history(user_id: str, limit: int = 30, offset: int = 0) -> list[dict[str, Any]]:
    """Return recent history entries (metadata only, no full state)."""
    pool = await _get_pool()
    if pool is None:
        return []

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, product_name, category, style_id, style_name, platform_id,
                   thumbnail, image_count, created_at, updated_at
            FROM project_history
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            user_id,
            limit,
            offset,
        )
    return [
        {
            "id": row["id"],
            "product_name": row["product_name"],
            "category": row["category"],
            "style_id": row["style_id"],
            "style_name": row["style_name"],
            "platform_id": row["platform_id"],
            "thumbnail": row["thumbnail"],
            "image_count": row["image_count"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else "",
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else "",
        }
        for row in rows
    ]


async def get_history(user_id: str, record_id: str) -> dict[str, Any] | None:
    """Return a single history entry including the full state JSON."""
    pool = await _get_pool()
    if pool is None:
        return None

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, product_name, category, style_id, style_name, platform_id,
                   thumbnail, image_count, state_json, created_at, updated_at
            FROM project_history
            WHERE user_id = $1 AND id = $2
            """,
            user_id,
            record_id,
        )
    if row is None:
        return None

    state = {}
    try:
        state = json.loads(row["state_json"])
    except (json.JSONDecodeError, TypeError):
        pass

    return {
        "id": row["id"],
        "product_name": row["product_name"],
        "category": row["category"],
        "style_id": row["style_id"],
        "style_name": row["style_name"],
        "platform_id": row["platform_id"],
        "thumbnail": row["thumbnail"],
        "image_count": row["image_count"],
        "state": state,
        "created_at": row["created_at"].isoformat() if row["created_at"] else "",
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else "",
    }


async def save_history(user_id: str, user_snapshot: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    """Insert or update a history record.  Returns the saved metadata."""
    pool = await _get_pool()
    if pool is None:
        return {"error": "database not configured"}

    record_id = record.get("id") or uuid4().hex
    now = datetime.now(UTC)
    state = record.get("state") or {}
    state_json = json.dumps(state, ensure_ascii=False, default=str)
    user_snapshot_json = json.dumps(user_snapshot or {}, ensure_ascii=False, default=str)

    product_name = record.get("product_name", "")
    category = record.get("category", "")
    style_id = record.get("style_id", "")
    style_name = record.get("style_name", "")
    platform_id = record.get("platform_id", "tmall")
    thumbnail = record.get("thumbnail", "")
    image_count = record.get("image_count", 0)

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO project_history
                (id, user_id, user_snapshot_json, product_name, category, style_id, style_name, platform_id,
                 thumbnail, image_count, state_json, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            ON CONFLICT (id) DO UPDATE SET
                user_snapshot_json = EXCLUDED.user_snapshot_json,
                product_name = EXCLUDED.product_name,
                category     = EXCLUDED.category,
                style_id     = EXCLUDED.style_id,
                style_name   = EXCLUDED.style_name,
                platform_id  = EXCLUDED.platform_id,
                thumbnail    = EXCLUDED.thumbnail,
                image_count  = EXCLUDED.image_count,
                state_json   = EXCLUDED.state_json,
                updated_at   = EXCLUDED.updated_at
            WHERE project_history.user_id = EXCLUDED.user_id
            """,
            record_id,
            user_id,
            user_snapshot_json,
            product_name,
            category,
            style_id,
            style_name,
            platform_id,
            thumbnail,
            image_count,
            state_json,
            now,
            now,
        )

    return {
        "id": record_id,
        "product_name": product_name,
        "category": category,
        "style_id": style_id,
        "style_name": style_name,
        "platform_id": platform_id,
        "thumbnail": thumbnail,
        "image_count": image_count,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }


async def delete_history(user_id: str, record_id: str) -> bool:
    """Delete a history record by ID.  Returns ``True`` if a row was removed."""
    pool = await _get_pool()
    if pool is None:
        return False

    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM project_history WHERE user_id = $1 AND id = $2",
            user_id,
            record_id,
        )
    return result == "DELETE 1"
