from __future__ import annotations
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.db.base import Base

class Group(Base):
    __tablename__ = "groups"
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    language: Mapped[str] = mapped_column(String(8), default="en")
    ads_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tokens = relationship("Token", back_populates="group", cascade="all, delete-orphan")
    adverts = relationship("Advert", back_populates="group", cascade="all, delete-orphan")

class Token(Base):
    __tablename__ = "tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("groups.chat_id", ondelete="CASCADE"), index=True)
    token_address: Mapped[str] = mapped_column(String(128), index=True)
    # Which on-chain trade source to use for buys.
    # Supported: auto | stonfi | dedust | gaspump
    source: Mapped[str] = mapped_column(String(32), default="auto")

    # Optional pool / pair address (recommended for DeDust and some launchpads).
    # If empty, the bot will try to auto-detect (best-effort) for some sources.
    pool_address: Mapped[str] = mapped_column(String(128), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    min_buy_ton: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())

    group = relationship("Group", back_populates="tokens")
    cursors = relationship("Cursor", back_populates="token", cascade="all, delete-orphan")
    processed = relationship("ProcessedTx", back_populates="token", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("chat_id", "token_address", name="uq_chat_token"),)

class Cursor(Base):
    __tablename__ = "cursors"
    token_id: Mapped[int] = mapped_column(Integer, ForeignKey("tokens.id", ondelete="CASCADE"), primary_key=True)
    cursor_value: Mapped[str] = mapped_column(String(256), default="")
    updated_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    token = relationship("Token", back_populates="cursors")

class ProcessedTx(Base):
    __tablename__ = "processed_txs"
    token_id: Mapped[int] = mapped_column(Integer, ForeignKey("tokens.id", ondelete="CASCADE"), primary_key=True)
    tx_hash: Mapped[str] = mapped_column(String(128), primary_key=True)
    seen_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())

    token = relationship("Token", back_populates="processed")

class Advert(Base):
    __tablename__ = "adverts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("groups.chat_id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    buttons_json: Mapped[str] = mapped_column(Text, default="[]")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    weight: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())

    group = relationship("Group", back_populates="adverts")

class AdminLog(Base):
    __tablename__ = "admin_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    admin_id: Mapped[int] = mapped_column(BigInteger, index=True)
    action: Mapped[str] = mapped_column(String(64))
    payload: Mapped[str] = mapped_column(Text, default="")
    ts: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
