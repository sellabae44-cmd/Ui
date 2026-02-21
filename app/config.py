from __future__ import annotations
import os
from dataclasses import dataclass

def _int(name: str, default: int) -> int:
    v = os.getenv(name)
    if not v:
        return default
    try:
        return int(v)
    except ValueError:
        return default

@dataclass(frozen=True)
class Settings:
    bot_token: str
    database_url: str
    poll_interval: int
    mock_trades: bool
    tonapi_key: str | None
    admin_chat_id: int | None

def load_settings() -> Settings:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    database_url = os.getenv("DATABASE_URL", "").strip()
    poll_interval = _int("POLL_INTERVAL", 6)
    mock_trades = os.getenv("MOCK_TRADES", "0").strip() == "1"
    tonapi_key = os.getenv("TONAPI_KEY", "").strip() or None
    raw = os.getenv("ADMIN_CHAT_ID", "").strip()
    admin_chat_id = int(raw) if raw.isdigit() else None
    return Settings(bot_token, database_url, poll_interval, mock_trades, tonapi_key, admin_chat_id)
