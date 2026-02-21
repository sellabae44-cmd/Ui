from __future__ import annotations
import asyncio, json, logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.core.formatter import TradeEvent, format_trade
from app.core.dedupe import seen_tx, mark_tx
from app.core.rate_limit import RateLimiter
from app.db.models import Token, Group, Cursor, Advert
from app.sources.mock_source import MockSource
from app.sources.tonapi_source import TonApiSource
from app.sources.stonfi_source import StonFiSource
from app.sources.dedust_source import DeDustSource

log = logging.getLogger("engine")

def _buttons_from_ad(buttons_json: str):
    try:
        items = json.loads(buttons_json or "[]")
    except Exception:
        items = []
    btns = []
    for it in items[:2]:
        t = (it.get("text") or "").strip()
        u = (it.get("url") or "").strip()
        if t and u:
            btns.append(InlineKeyboardButton(text=t, url=u))
    return btns

async def _pick_ad(session, chat_id: int):
    res = await session.execute(select(Advert).where(Advert.chat_id == chat_id, Advert.is_active == True).order_by(Advert.id.asc()))
    return res.scalars().first()

async def _get_or_create_group(session, chat_id: int) -> Group:
    g = await session.get(Group, chat_id)
    if g is None:
        g = Group(chat_id=chat_id, language="en", ads_enabled=True)
        session.add(g)
    return g

async def _get_cursor(session, token_id: int):
    c = await session.get(Cursor, token_id)
    return c.cursor_value if c else None

async def _set_cursor(session, token_id: int, cursor_value: str | None):
    if cursor_value is None:
        return
    c = await session.get(Cursor, token_id)
    if c is None:
        session.add(Cursor(token_id=token_id, cursor_value=cursor_value))
    else:
        c.cursor_value = cursor_value

class Engine:
    def __init__(self, bot: Bot, sessionmaker: async_sessionmaker, poll_interval: int, mock_trades: bool, tonapi_key: str | None):
        self.bot = bot
        self.sm = sessionmaker
        self.poll_interval = max(3, poll_interval)
        self.ratelimit = RateLimiter(20.0)
        self.sources = {
            "mock": MockSource(),
            "stonfi": StonFiSource(),
            "dedust": DeDustSource(),
            # gaspump is best-effort: many GasPump/SunPump tokens end up trading on DeDust/STONfi.
            "gaspump": DeDustSource(gaspump_mode=True),
        }
        if tonapi_key:
            self.sources["tonapi"] = TonApiSource(tonapi_key)
        # Prefer real DEX indexers by default if present.
        if mock_trades:
            self.default_source = "mock"
        else:
            self.default_source = "stonfi" if "stonfi" in self.sources else ("tonapi" if tonapi_key else "mock")
        if not tonapi_key and not mock_trades:
            log.info("TONAPI_KEY not set. Using public DEX APIs (STON.fi/DeDust) where possible.")

    async def run_forever(self):
        while True:
            try:
                await self.tick()
            except Exception:
                log.exception("Engine tick failed")
            await asyncio.sleep(self.poll_interval)

    async def tick(self):
        async with self.sm() as session:
            res = await session.execute(select(Token).where(Token.is_active == True))
            token_ids = [t.id for t in res.scalars().all()]
        for tid in token_ids:
            await self.process_token(tid)

    async def process_token(self, token_id: int):
        async with self.sm() as session:
            token = await session.get(Token, token_id)
            if not token or not token.is_active:
                return
            group = await _get_or_create_group(session, token.chat_id)
            source_name = token.source if token.source != "auto" else self.default_source
            source = self.sources.get(source_name) or self.sources[self.default_source]
            cursor = await _get_cursor(session, token.id)

            result = await source.fetch(token.token_address, cursor, token.pool_address or "")
            for ev in (result.events or []):
                tx_hash = str(ev.get("tx_hash", "")).strip()
                if not tx_hash:
                    continue
                if await seen_tx(session, token.id, tx_hash):
                    continue

                await mark_tx(session, token.id, tx_hash)
                await _set_cursor(session, token.id, result.next_cursor or cursor)
                await session.commit()

                event = TradeEvent(
                    token_address=token.token_address,
                    tx_hash=tx_hash,
                    buyer=str(ev.get("buyer", "")),
                    ton_amount=float(ev.get("ton_amount", 0.0)),
                    token_amount=float(ev.get("token_amount", 0.0)),
                    is_buy=bool(ev.get("is_buy", True)),
                    price_usd=ev.get("price_usd"),
                    mcap_usd=ev.get("mcap_usd"),
                )
                msg = format_trade(event)

                markup = None
                if group.ads_enabled:
                    ad = await _pick_ad(session, token.chat_id)
                    if ad:
                        btns = _buttons_from_ad(ad.buttons_json)
                        if btns:
                            markup = InlineKeyboardMarkup(inline_keyboard=[btns])
                        msg = msg + "\n\n📢 " + ad.text.strip()

                await self.ratelimit.wait()
                try:
                    await self.bot.send_message(token.chat_id, msg, reply_markup=markup, disable_web_page_preview=True)
                except Exception:
                    log.exception("Failed to send message to chat %s", token.chat_id)
