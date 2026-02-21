from __future__ import annotations
import os
from dataclasses import dataclass


def _normalize_db_url(url: str) -> str:
    """Normalize DATABASE_URL for SQLAlchemy async engines.

    Railway Postgres typically returns a *sync* URL like:
      postgresql://user:pass@host:port/db
    SQLAlchemy async expects:
      postgresql+asyncpg://user:pass@host:port/db

    For SQLite, we use sqlite+aiosqlite.
    """
    u = (url or "").strip()
    if not u:
        return ""
    if u.startswith("postgres://"):
        return "postgresql+asyncpg://" + u[len("postgres://"):]
    if u.startswith("postgresql://"):
        return "postgresql+asyncpg://" + u[len("postgresql://"):]
    if u.startswith("sqlite:///"):
        # Upgrade to async driver
        return "sqlite+aiosqlite:///" + u[len("sqlite:///"):]
    return u

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
    sqlite_path: str
    poll_interval: int
    mock_trades: bool
    tonapi_key: str | None
    admin_chat_id: int | None

    def effective_database_url(self) -> str:
        """Return a working SQLAlchemy async database URL.

        If DATABASE_URL is missing, we fall back to a local SQLite DB file.
        """
        if self.database_url and self.database_url.strip():
            return _normalize_db_url(self.database_url)
        # Local fallback (no external DB needed)
        path = self.sqlite_path.strip() or "/tmp/spyton.db"
        # Ensure 3 slashes for absolute paths
        if path.startswith("/"):
            return f"sqlite+aiosqlite:///{path}"
        return f"sqlite+aiosqlite:///" + path

def load_settings() -> Settings:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    database_url = os.getenv("DATABASE_URL", "").strip()
    sqlite_path = os.getenv("SQLITE_PATH", "/tmp/spyton.db").strip()
    poll_interval = _int("POLL_INTERVAL", 6)
    mock_trades = os.getenv("MOCK_TRADES", "0").strip() == "1"
    tonapi_key = os.getenv("TONAPI_KEY", "").strip() or None
    raw = os.getenv("ADMIN_CHAT_ID", "").strip()
    admin_chat_id = int(raw) if raw.isdigit() else None
    return Settings(bot_token, database_url, sqlite_path, poll_interval, mock_trades, tonapi_key, admin_chat_id)
