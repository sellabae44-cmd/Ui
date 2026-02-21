from __future__ import annotations
import aiohttp
from app.sources.base import SourceResult

class TonApiSource:
    name = "tonapi"
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def fetch(self, token_address: str, cursor: str | None, pool_address: str = "") -> SourceResult:
        # Placeholder: implement with your TonAPI endpoint.
        # Intentionally returns empty to avoid false promises about a specific endpoint.
        return SourceResult(events=[], next_cursor=cursor)
