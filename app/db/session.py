from __future__ import annotations
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import Settings

def make_engine(settings: Settings):
    return create_async_engine(settings.database_url, pool_pre_ping=True)

def make_sessionmaker(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
