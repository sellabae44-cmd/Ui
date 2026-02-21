from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol

@dataclass
class SourceResult:
    events: list[dict]
    next_cursor: str | None

class TradeSource(Protocol):
    name: str
    async def fetch(self, token_address: str, cursor: str | None, pool_address: str = "") -> SourceResult: ...
