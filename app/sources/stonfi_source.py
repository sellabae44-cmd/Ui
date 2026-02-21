from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Iterable, List, Tuple

import aiohttp

from app.sources.base import SourceResult

log = logging.getLogger(__name__)

# Public STON.fi export endpoints (see STON.fi API reference: Export / DexScreener)
STONFI_LATEST_BLOCK_URL = "https://api.ston.fi/export/dexscreener/v1/latest-block"
STONFI_EVENTS_URL = "https://api.ston.fi/export/dexscreener/v1/events"


def _walk_values(obj: Any) -> Iterable[Any]:
    """Yield all primitive values from a nested structure."""
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_values(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_values(v)
    else:
        yield obj


def _find_first_int(obj: Any) -> int | None:
    for v in _walk_values(obj):
        if isinstance(v, bool):
            continue
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return int(v)
        if isinstance(v, str) and v.isdigit():
            try:
                return int(v)
            except Exception:
                pass
    return None


def _safe_float(x: Any) -> float | None:
    try:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return float(x)
        if isinstance(x, str):
            s = x.replace(",", "").strip()
            return float(s)
    except Exception:
        return None
    return None


def _string_contains_token(event: Dict[str, Any], token: str) -> bool:
    token = token.lower().strip()
    if not token:
        return False
    # Fast path: stringify once.
    try:
        blob = json.dumps(event, ensure_ascii=False).lower()
        return token in blob
    except Exception:
        # Fallback: walk values
        for v in _walk_values(event):
            if isinstance(v, str) and token in v.lower():
                return True
        return False


def _pick(event: Dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in event:
            return event[k]
    return None


def _guess_amounts(event: Dict[str, Any]) -> Tuple[float | None, float | None]:
    """Best-effort: return (ton_amount, token_amount) for a swap-like event.

    STON.fi export format can vary; we try common DexScreener-style keys.
    If we can't confidently determine, return (None, None).
    """
    # Common patterns
    # - amountIn/amountOut with tokenInSymbol/tokenOutSymbol
    a_in = _safe_float(_pick(event, "amountIn", "amount_in", "inAmount", "in_amount"))
    a_out = _safe_float(_pick(event, "amountOut", "amount_out", "outAmount", "out_amount"))
    sym_in = _pick(event, "tokenInSymbol", "token_in_symbol", "inSymbol", "symbolIn")
    sym_out = _pick(event, "tokenOutSymbol", "token_out_symbol", "outSymbol", "symbolOut")
    if isinstance(sym_in, str) and isinstance(sym_out, str) and a_in is not None and a_out is not None:
        if sym_in.upper() == "TON":
            return a_in, a_out
        if sym_out.upper() == "TON":
            return a_out, a_in

    # - amount0/amount1 + token0Symbol/token1Symbol
    a0 = _safe_float(_pick(event, "amount0", "amount_0", "token0Amount", "token0_amount"))
    a1 = _safe_float(_pick(event, "amount1", "amount_1", "token1Amount", "token1_amount"))
    s0 = _pick(event, "token0Symbol", "token0_symbol", "symbol0")
    s1 = _pick(event, "token1Symbol", "token1_symbol", "symbol1")
    if isinstance(s0, str) and isinstance(s1, str) and a0 is not None and a1 is not None:
        if s0.upper() == "TON":
            return a0, a1
        if s1.upper() == "TON":
            return a1, a0

    # - volumeUSD etc only; we can't.
    return None, None


class StonFiSource:
    name = "stonfi"

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        self._external_session = session

    async def _get_latest_block(self, session: aiohttp.ClientSession) -> int:
        async with session.get(STONFI_LATEST_BLOCK_URL, timeout=aiohttp.ClientTimeout(total=15)) as r:
            r.raise_for_status()
            data = await r.json(content_type=None)
        num = _find_first_int(data)
        if num is None:
            raise RuntimeError(f"STON.fi latest-block response did not contain a block number: {data}")
        return int(num)

    async def _get_events(
        self, session: aiohttp.ClientSession, from_block: int, to_block: int
    ) -> List[Dict[str, Any]]:
        # Different deployments have used different param names; try a few.
        param_sets = [
            {"fromBlock": from_block, "toBlock": to_block},
            {"from_block": from_block, "to_block": to_block},
            {"blockNumberFrom": from_block, "blockNumberTo": to_block},
        ]
        last_err: Exception | None = None
        for params in param_sets:
            try:
                async with session.get(STONFI_EVENTS_URL, params=params, timeout=aiohttp.ClientTimeout(total=20)) as r:
                    if r.status >= 400:
                        txt = await r.text()
                        raise RuntimeError(f"STON.fi events HTTP {r.status}: {txt[:200]}")
                    data = await r.json(content_type=None)
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    # common wrappers
                    if isinstance(data.get("events"), list):
                        return data["events"]
                    if isinstance(data.get("data"), list):
                        return data["data"]
                return []
            except Exception as e:
                last_err = e
                continue
        raise last_err or RuntimeError("Failed to fetch STON.fi events")

    async def fetch(self, token_address: str, cursor: str | None, pool_address: str = "") -> SourceResult:
        # Cursor is last processed block.
        try:
            last_block = int(cursor) if cursor else 0
        except Exception:
            last_block = 0

        owned = False
        session = self._external_session
        if session is None:
            session = aiohttp.ClientSession()
            owned = True
        try:
            latest = await self._get_latest_block(session)
            # Start from last_block+1 to avoid repeats. If first time, look back a bit.
            start = (last_block + 1) if last_block > 0 else max(0, latest - 25)
            # Cap range to keep load reasonable.
            end = latest
            if end - start > 50:
                start = end - 50

            raw_events = await self._get_events(session, start, end)
            events: List[Dict[str, Any]] = []
            for ev in raw_events:
                if not isinstance(ev, dict):
                    continue
                # Filter by token address if possible.
                if not _string_contains_token(ev, token_address):
                    continue

                # Only keep swap-like events if type is present.
                ev_type = str(_pick(ev, "type", "eventType", "kind", "event" ) or "").lower()
                if ev_type and not any(x in ev_type for x in ("swap", "trade", "buy", "sell")):
                    continue

                ton_amount, token_amount = _guess_amounts(ev)
                if ton_amount is None or token_amount is None:
                    # If we can't parse amounts, skip (better than posting wrong numbers).
                    continue

                tx_hash = _pick(ev, "txHash", "tx_hash", "transactionHash", "hash") or ""
                buyer = _pick(ev, "trader", "maker", "sender", "buyer", "user", "from") or ""
                # Best-effort buy detection: if TON is input, it's a buy.
                sym_in = _pick(ev, "tokenInSymbol", "token_in_symbol", "inSymbol", "symbolIn")
                is_buy = True
                if isinstance(sym_in, str) and sym_in.upper() != "TON":
                    # Token->TON swap is a sell.
                    is_buy = False

                if not is_buy:
                    continue

                events.append(
                    {
                        "tx_hash": str(tx_hash),
                        "buyer": str(buyer),
                        "ton_amount": float(ton_amount),
                        "token_amount": float(token_amount),
                        "is_buy": True,
                        "source": "stonfi",
                    }
                )

            # Next cursor is the latest block we scanned.
            return SourceResult(events=events, next_cursor=str(end))
        finally:
            if owned:
                await session.close()
