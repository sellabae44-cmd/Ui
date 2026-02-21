from __future__ import annotations
import asyncio, logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from app.config import load_settings
from app.db.session import make_engine, make_sessionmaker
from app.db.init_db import init_db
from app.tg.router import setup_dispatcher
from app.core.engine import Engine

logging.basicConfig(level=logging.INFO)

async def main() -> None:
    load_dotenv()
    settings = load_settings()
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN missing")

    # DATABASE_URL is optional. If not provided, we automatically fall back to
    # a local SQLite database file so deployment is zero-setup.

    engine = make_engine(settings)
    await init_db(engine)
    db_sm = make_sessionmaker(engine)

    bot = Bot(settings.bot_token)

    # aiogram v3 Bot is not dict-like, so we attach our shared objects as attributes.
    setattr(bot, "db_sm", db_sm)
    setattr(bot, "settings", settings)

    dp = Dispatcher(storage=MemoryStorage())
    setup_dispatcher(dp)

    trade_engine = Engine(bot, db_sm, settings.poll_interval, settings.mock_trades, settings.tonapi_key)
    asyncio.create_task(trade_engine.run_forever())

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
