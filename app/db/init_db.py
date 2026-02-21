from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text
from app.db.base import Base
from app.db import models  # noqa: F401


async def _best_effort_migrations(engine: AsyncEngine) -> None:
    """Lightweight migrations for SQLite deployments.

    This project uses create_all() by default. For hobby/self-host installs, users
    often keep a persistent SQLite volume; in that case we add new columns using
    ALTER TABLE (safe if the column already exists).
    """
    async with engine.begin() as conn:
        # Add Token.pool_address if missing
        try:
            await conn.execute(text("ALTER TABLE tokens ADD COLUMN pool_address VARCHAR(128) DEFAULT ''"))
        except Exception:
            pass

async def init_db(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await _best_effort_migrations(engine)
