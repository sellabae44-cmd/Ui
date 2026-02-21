from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from app.tg.states import AddToken
from app.tg.utils import looks_like_ton_address
from app.db.models import Group, Token, AdminLog

router = Router()

def token_row_kb(token_id: int, is_active: bool):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=("🟢 Active" if is_active else "⚫️ Paused"), callback_data=f"token:toggle:{token_id}"),
         InlineKeyboardButton(text="🗑 Delete", callback_data=f"token:del:{token_id}")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="menu:tokens")]
    ])

@router.callback_query(F.data == "tokens:add")
async def add_token(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AddToken.waiting_address)
    await cb.message.answer("Send token address (EQ...):")
    await cb.answer()

def source_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚡ Auto", callback_data="addsrc:auto"),
            InlineKeyboardButton(text="🌀 STON.fi", callback_data="addsrc:stonfi"),
        ],
        [
            InlineKeyboardButton(text="🧩 DeDust", callback_data="addsrc:dedust"),
            InlineKeyboardButton(text="🚀 GasPump", callback_data="addsrc:gaspump"),
        ],
        [InlineKeyboardButton(text="⬅️ Cancel", callback_data="addsrc:cancel")],
    ])


@router.message(AddToken.waiting_address)
async def got_address(message: Message, state: FSMContext):
    addr = (message.text or "").strip()
    if not looks_like_ton_address(addr):
        await message.answer("❌ Invalid TON address. Send EQ... again.")
        return
    await state.update_data(token_address=addr)
    await state.set_state(AddToken.waiting_source)
    await message.answer(
        "Choose where to track real buys for this token:\n"
        "• Auto: best-effort (STON.fi then DeDust)\n"
        "• STON.fi: swaps on STON.fi\n"
        "• DeDust: swaps on DeDust (may require pool address)\n"
        "• GasPump: best-effort (many tokens trade on DeDust after launch)\n",
        reply_markup=source_kb(),
    )


@router.callback_query(AddToken.waiting_source, F.data.startswith("addsrc:"))
async def pick_source(cb: CallbackQuery, state: FSMContext):
    src = cb.data.split(":", 1)[1]
    if src == "cancel":
        await state.clear()
        await cb.message.answer("Cancelled.")
        await cb.answer()
        return
    await state.update_data(source=src)
    if src in ("dedust", "gaspump"):
        await state.set_state(AddToken.waiting_pool)
        await cb.message.answer(
            "Optional: send pool/pair address for faster & accurate tracking.\n"
            "If you don't have it, send `skip` and the bot will try to auto-detect.",
            parse_mode="Markdown",
        )
    else:
        # Save now
        data = await state.get_data()
        await _save_token(cb.message, data, pool_address="")
        await state.clear()
    await cb.answer()


@router.message(AddToken.waiting_pool)
async def got_pool(message: Message, state: FSMContext):
    txt = (message.text or "").strip()
    pool = "" if txt.lower() == "skip" else txt
    data = await state.get_data()
    await _save_token(message, data, pool_address=pool)
    await state.clear()


async def _save_token(message_or_cbmsg: Message, data: dict, pool_address: str):
    # db_sm is attached on the Bot instance in main.py (aiogram v3 Bot is not dict-like)
    db_sm = getattr(message_or_cbmsg.bot, "db_sm", None)
    if db_sm is None:
        raise RuntimeError("DB sessionmaker not attached to bot")
    addr = data.get("token_address")
    src = data.get("source") or "auto"
    async with db_sm() as session:
        g = await session.get(Group, message_or_cbmsg.chat.id)
        if g is None:
            g = Group(chat_id=message_or_cbmsg.chat.id)
            session.add(g)
        res = await session.execute(select(Token).where(Token.chat_id==message_or_cbmsg.chat.id, Token.token_address==addr))
        if res.scalar_one_or_none():
            await message_or_cbmsg.answer("✅ Token already added.")
            return
        t = Token(chat_id=message_or_cbmsg.chat.id, token_address=addr, source=src, pool_address=pool_address or "", is_active=True)
        session.add(t)
        session.add(AdminLog(chat_id=message_or_cbmsg.chat.id, admin_id=message_or_cbmsg.from_user.id, action="token_add", payload=f"{addr}|{src}|{pool_address or ''}"))
        await session.commit()
        await message_or_cbmsg.answer("✅ Token added and tracking started.")

@router.callback_query(F.data == "tokens:list")
async def list_tokens(cb: CallbackQuery, db_sm):
    async with db_sm() as session:
        res = await session.execute(select(Token).where(Token.chat_id==cb.message.chat.id).order_by(Token.id.desc()))
        tokens = res.scalars().all()
    if not tokens:
        await cb.message.answer("No tokens yet. Add one first.")
        await cb.answer()
        return
    for t in tokens[:20]:
        await cb.message.answer(f"Token #{t.id}\n{t.token_address}\nStatus: {'ACTIVE' if t.is_active else 'PAUSED'}", reply_markup=token_row_kb(t.id, t.is_active))
    await cb.answer()

@router.callback_query(F.data.startswith("token:toggle:"))
async def toggle_token(cb: CallbackQuery, db_sm):
    tid = int(cb.data.split(":")[-1])
    async with db_sm() as session:
        t = await session.get(Token, tid)
        if not t or t.chat_id != cb.message.chat.id:
            await cb.answer("Not found", show_alert=True); return
        t.is_active = not t.is_active
        session.add(AdminLog(chat_id=cb.message.chat.id, admin_id=cb.from_user.id, action="token_toggle", payload=f"{tid}:{t.is_active}"))
        await session.commit()
        await cb.message.edit_reply_markup(reply_markup=token_row_kb(t.id, t.is_active))
    await cb.answer("Updated")

@router.callback_query(F.data.startswith("token:del:"))
async def delete_token(cb: CallbackQuery, db_sm):
    tid = int(cb.data.split(":")[-1])
    async with db_sm() as session:
        t = await session.get(Token, tid)
        if not t or t.chat_id != cb.message.chat.id:
            await cb.answer("Not found", show_alert=True); return
        await session.delete(t)
        session.add(AdminLog(chat_id=cb.message.chat.id, admin_id=cb.from_user.id, action="token_delete", payload=str(tid)))
        await session.commit()
    await cb.message.answer("🗑 Token deleted.")
    await cb.answer()
