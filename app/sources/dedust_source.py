from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

import aiohttp

from app.sources.base import SourceResult

log = logging.getLogger(__name__)


DEDUST_API_BASE = "https://api.dedust.io/v2"


def _parse_cursor(cursor: str | None) -> int:
    """Cursor for DeDust trades: unix timestamp (seconds)."""
    if not cursor:
        return 0
    try:
        return int(cursor)
    except Exception:
        return 0


def _guess_ton(trade: Dict[str, Any]) -> Tuple[float | None, float | None, bool]:
    """Try to extract (ton_amount, token_amount, is_buy) from a DeDust trade."""
    # DeDust trade objects have varied shapes across versions.
    # We attempt to read generic in/out amounts and detect TON by symbol.
    tin = trade.get("amount_in") or trade.get("amountIn") or trade.get("in") or {}
    tout = trade.get("amount_out") or trade.get("amountOut") or trade.get("out") or {}

    # Sometimes the amounts are nested.
    def _amt(x: Any) -> float | None:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return float(x)
        if isinstance(x, str):
            try:
                return float(x)
            except Exception:
                return None
        if isinstance(x, dict):
            for k in ("value", "amount", "ui_amount", "uiAmount"):
                if k in x:
                    return _amt(x[k])
        return None

    def _sym(x: Any) -> str | None:
        if isinstance(x, dict):
            return x.get("symbol") or x.get("ticker")
        return None

    sym_in = _sym(tin)
    sym_out = _sym(tout)
    amt_in = _amt(tin)
    amt_out = _amt(tout)

    # If symbols exist, easiest path
    if sym_in and sym_out and amt_in is not None and amt_out is not None:
        is_buy = sym_in.upper() == "TON" and sym_out.upper() != "TON"
        if is_buy:
            return amt_in, amt_out, True
        is_sell = sym_out.upper() == "TON" and sym_in.upper() != "TON"
        if is_sell:
            return amt_out, amt_in, False

    # Fallback: some responses have explicit ton/token fields
    for k in ("ton_amount", "tonAmount"):
        if k in trade:
            try:
                ton_amt = float(trade[k])
                token_amt = float(trade.get("token_amount") or trade.get("tokenAmount") or 0)
                return ton_amt, token_amt if token_amt else None, True
            except Exception:
                pass

    return None, None, True


class DeDustSource:
    name = "dedust"

    def __init__(
        self,
        session: aiohttp.ClientSession | None = None,
        gaspump_mode: bool = False,
    ):
        # Engine normally injects a shared aiohttp session. If not provided
        # we lazily create one on first use (useful for minimal deployments).
        self.session: aiohttp.ClientSession | None = session
        self._own_session: bool = session is None
        # Some deployments treat DeDust swaps from GasPump pools slightly differently.
        # We keep the flag so engine can instantiate two variants.
        self.gaspump_mode: bool = gaspump_mode

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
            self._own_session = True
        return self.session

    async def _autodetect_pool(self, token_address: str) -> str | None:
        """Best-effort pool discovery.

        DeDust API supports listing pools; we try a few common query parameter shapes.
        If discovery fails, admins can provide pool address manually.
        """
        token_address = token_address.strip()

        candidates: List[Dict[str, Any]] = []
        tried_urls = [
            f"{DEDUST_API_BASE}/pools?asset={token_address}",
            f"{DEDUST_API_BASE}/pools?token={token_address}",
            f"{DEDUST_API_BASE}/pools?limit=500",
            f"{DEDUST_API_BASE}/pools",
        ]

        session = await self._ensure_session()

        for url in tried_urls:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as r:
                    if r.status != 200:
                        continue
                    data = await r.json()
                    # Could be list or {pools:[...]}
                    if isinstance(data, list):
                        candidates = data
                    elif isinstance(data, dict):
                        candidates = data.get("pools") or data.get("data") or []
                    else:
                        candidates = []
                    if candidates:
                        break
            except Exception:
                continue

        if not candidates:
            return None

        # Pick a pool that contains the token address in any nested value
        def contains_token(obj: Any) -> bool:
            if isinstance(obj, dict):
                return any(contains_token(v) for v in obj.values())
            if isinstance(obj, list):
                return any(contains_token(v) for v in obj)
            if isinstance(obj, str):
                return obj.strip() == token_address
            return False

        for p in candidates:
            if contains_token(p):
                addr = p.get("address") or p.get("pool_address") or p.get("pool")
                if isinstance(addr, str) and addr:
                    return addr
        return None

    async def fetch(self, token_address: str, cursor: str | None, pool_address: str = "") -> SourceResult:
        since_ts = _parse_cursor(cursor)

        pool = (pool_address or "").strip()
        if not pool:
            pool = await self._autodetect_pool(token_address) or ""

        if not pool:
            # Can't fetch without pool
            log.info("DeDust pool not set and autodetect failed for %s", token_address)
            return SourceResult(events=[], next_cursor=cursor)

        url = f"{DEDUST_API_BASE}/pools/{pool}/trades"
        session = await self._ensure_session()
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as r:
                if r.status != 200:
                    text = await r.text()
                    log.warning("DeDust trades fetch failed (%s): %s", r.status, text[:200])
                    return SourceResult(events=[], next_cursor=cursor)
                data = await r.json()
        except Exception as e:
            log.warning("DeDust trades fetch error: %s", e)
            return SourceResult(events=[], next_cursor=cursor)

        trades: List[Dict[str, Any]]
        if isinstance(data, list):
            trades = data
        elif isinstance(data, dict):
            trades = data.get("trades") or data.get("data") or []
        else:
            trades = []

        events: List[Dict[str, Any]] = []
        max_ts = since_ts

        for t in trades:
            ts = t.get("timestamp") or t.get("time") or t.get("ts")
            try:
                ts_i = int(ts) if ts is not None else 0
            except Exception:
                ts_i = 0

            if ts_i and ts_i <= since_ts:
                continue
            max_ts = max(max_ts, ts_i)

            tx_hash = t.get("tx_hash") or t.get("txHash") or t.get("hash") or ""
            buyer = t.get("trader") or t.get("sender") or t.get("user") or ""
            ton_amt, token_amt, is_buy = _guess_ton(t)
            if ton_amt is None or token_amt is None:
                continue

            events.append(
                {
                    "tx_hash": str(tx_hash),
                    "buyer": str(buyer),
                    "ton_amount": float(ton_amt),
                    "token_amount": float(token_amt),
                    "is_buy": bool(is_buy),
                }
            )

        next_cursor = str(max_ts) if max_ts > since_ts else cursor
        return SourceResult(events=events, next_cursor=next_cursor)
