from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import ProcessedTx

async def seen_tx(session: AsyncSession, token_id: int, tx_hash: str) -> bool:
    res = await session.execute(
        select(ProcessedTx).where(ProcessedTx.token_id == token_id, ProcessedTx.tx_hash == tx_hash)
    )
    return res.scalar_one_or_none() is not None

async def mark_tx(session: AsyncSession, token_id: int, tx_hash: str) -> None:
    session.add(ProcessedTx(token_id=token_id, tx_hash=tx_hash))
