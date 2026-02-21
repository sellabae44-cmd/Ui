from __future__ import annotations
from dataclasses import dataclass
from aiogram.utils.markdown import hbold, hlink

@dataclass
class TradeEvent:
    token_address: str
    tx_hash: str
    buyer: str
    ton_amount: float
    token_amount: float
    is_buy: bool
    price_usd: float | None = None
    mcap_usd: float | None = None

def format_trade(event: TradeEvent) -> str:
    side = "🟢 BUY" if event.is_buy else "🔴 SELL"
    header = f"🛰️ {hbold('SpyTON Intel')} — {hbold(side)}"
    txn = hlink("Txn", f"https://tonviewer.com/transaction/{event.tx_hash}")
    buyer_link = hlink("Buyer", f"https://tonviewer.com/{event.buyer}") if event.buyer else "Buyer"
    lines = [
        header,
        "",
        f"💎 {event.ton_amount:,.4f} TON",
        f"🪙 {event.token_amount:,.4f} TOKENS",
        "",
        f"👤 {buyer_link} • {txn}",
    ]
    if event.mcap_usd is not None:
        lines.append(f"📊 MCap: ${event.mcap_usd:,.0f}")
    if event.price_usd is not None:
        lines.append(f"💵 Price: ${event.price_usd:,.6f}")
    return "\n".join(lines)
