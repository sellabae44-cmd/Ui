from __future__ import annotations
import asyncio, time

class RateLimiter:
    def __init__(self, per_second: float = 20.0):
        self.per_second = max(1.0, per_second)
        self._lock = asyncio.Lock()
        self._next = 0.0

    async def wait(self):
        async with self._lock:
            now = time.monotonic()
            if now < self._next:
                await asyncio.sleep(self._next - now)
            self._next = max(self._next, now) + (1.0 / self.per_second)
