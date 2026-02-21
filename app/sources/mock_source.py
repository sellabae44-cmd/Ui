from __future__ import annotations
import random, time, hashlib
from app.sources.base import SourceResult

class MockSource:
    name = "mock"

    async def fetch(self, token_address: str, cursor: str | None, pool_address: str = "") -> SourceResult:
        n = random.choice([0, 1, 2])
        evs = []
        for _ in range(n):
            now = int(time.time())
            seed = f"{token_address}:{now}:{random.random()}".encode()
            tx = hashlib.sha256(seed).hexdigest()
            buyer = "EQ" + hashlib.md5(seed).hexdigest()[:44]
            ton_amount = round(random.uniform(0.05, 8.0), 4)
            token_amount = round(ton_amount * random.uniform(1000, 50000), 4)
            evs.append({"tx_hash": tx, "buyer": buyer, "ton_amount": ton_amount, "token_amount": token_amount, "is_buy": True})
        return SourceResult(events=evs, next_cursor=str(int(time.time())))
