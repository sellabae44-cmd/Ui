import json
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from app.tg.states import CreateAd
from app.db.models import Group, Advert, AdminLog

router = Router()

def ad_kb(ad_id: int, is_active: bool):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=("✅ Active" if is_active else "⛔️ Disabled"), callback_data=f"ad:toggle:{ad_id}"),
         InlineKeyboardButton(text="🗑 Delete", callback_data=f"ad:del:{ad_id}")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="menu:ads")]
    ])

@router.callback_query(F.data == "ads:toggle")
async def toggle_ads(cb: CallbackQuery, db_sm):
    async with db_sm() as session:
        g = await session.get(Group, cb.message.chat.id)
        if g is None:
            g = Group(chat_id=cb.message.chat.id)
            session.add(g)
        g.ads_enabled = not g.ads_enabled
        session.add(AdminLog(chat_id=cb.message.chat.id, admin_id=cb.from_user.id, action="ads_enabled", payload=str(g.ads_enabled)))
        await session.commit()
        status = "ON" if g.ads_enabled else "OFF"
    await cb.message.answer(f"📢 Intel Ads: {status}")
    await cb.answer("Updated")

@router.callback_query(F.data == "ads:create")
async def create_ad(cb: CallbackQuery, state: FSMContext):
    await state.set_state(CreateAd.waiting_text)
    await cb.message.answer("Send advert text (1-400 chars):")
    await cb.answer()

@router.message(CreateAd.waiting_text)
async def ad_text(message: Message, state: FSMContext):
    txt = (message.text or "").strip()
    if not (1 <= len(txt) <= 400):
        await message.answer("Text must be 1-400 chars. Send again.")
        return
    await state.update_data(text=txt)
    await state.set_state(CreateAd.waiting_button_text)
    await message.answer("Optional: send button text or type `skip`:")

@router.message(CreateAd.waiting_button_text)
async def ad_btn_text(message: Message, state: FSMContext):
    bt = (message.text or "").strip()
    if bt.lower() == "skip":
        await state.update_data(button_text=None, button_url=None)
        await _save(message, state)
        return
    if len(bt) > 40:
        await message.answer("Max 40 chars. Send again or `skip`.")
        return
    await state.update_data(button_text=bt)
    await state.set_state(CreateAd.waiting_button_url)
    await message.answer("Send button URL (https://...)")

@router.message(CreateAd.waiting_button_url)
async def ad_btn_url(message: Message, state: FSMContext):
    url = (message.text or "").strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        await message.answer("URL must start with http:// or https://. Send again.")
        return
    await state.update_data(button_url=url)
    await _save(message, state)

async def _save(message: Message, state: FSMContext):
    data = await state.get_data()
    text = data.get("text")
    bt = data.get("button_text")
    bu = data.get("button_url")
    buttons = []
    if bt and bu:
        buttons.append({"text": bt, "url": bu})

    db_sm = getattr(message.bot, "db_sm", None)
    if db_sm is None:
        raise RuntimeError("DB sessionmaker not attached to bot")

    async with db_sm() as session:
        g = await session.get(Group, message.chat.id)
        if g is None:
            g = Group(chat_id=message.chat.id)
            session.add(g)
        session.add(Advert(chat_id=message.chat.id, text=text, buttons_json=json.dumps(buttons), is_active=True))
        session.add(AdminLog(chat_id=message.chat.id, admin_id=message.from_user.id, action="ad_create", payload=text[:80]))
        await session.commit()

    await message.answer("✅ Advert created.")
    await state.clear()

@router.callback_query(F.data == "ads:list")
async def list_ads(cb: CallbackQuery):
    db_sm = getattr(cb.bot, "db_sm", None)
    if db_sm is None:
        raise RuntimeError("DB sessionmaker not attached to bot")
    async with db_sm() as session:
        res = await session.execute(select(Advert).where(Advert.chat_id==cb.message.chat.id).order_by(Advert.id.desc()))
        ads = res.scalars().all()
    if not ads:
        await cb.message.answer("No adverts yet.")
        await cb.answer()
        return
    for a in ads[:20]:
        await cb.message.answer(f"Advert #{a.id}\nStatus: {'ACTIVE' if a.is_active else 'DISABLED'}\n\n{a.text}", reply_markup=ad_kb(a.id, a.is_active))
    await cb.answer()

@router.callback_query(F.data.startswith("ad:toggle:"))
async def toggle_ad(cb: CallbackQuery):
    db_sm = getattr(cb.bot, "db_sm", None)
    if db_sm is None:
        raise RuntimeError("DB sessionmaker not attached to bot")
    ad_id = int(cb.data.split(":")[-1])
    async with db_sm() as session:
        a = await session.get(Advert, ad_id)
        if not a or a.chat_id != cb.message.chat.id:
            await cb.answer("Not found", show_alert=True); return
        a.is_active = not a.is_active
        session.add(AdminLog(chat_id=cb.message.chat.id, admin_id=cb.from_user.id, action="ad_toggle", payload=f"{ad_id}:{a.is_active}"))
        await session.commit()
        await cb.message.edit_reply_markup(reply_markup=ad_kb(a.id, a.is_active))
    await cb.answer("Updated")

@router.callback_query(F.data.startswith("ad:del:"))
async def delete_ad(cb: CallbackQuery):
    db_sm = getattr(cb.bot, "db_sm", None)
    if db_sm is None:
        raise RuntimeError("DB sessionmaker not attached to bot")
    ad_id = int(cb.data.split(":")[-1])
    async with db_sm() as session:
        a = await session.get(Advert, ad_id)
        if not a or a.chat_id != cb.message.chat.id:
            await cb.answer("Not found", show_alert=True); return
        await session.delete(a)
        session.add(AdminLog(chat_id=cb.message.chat.id, admin_id=cb.from_user.id, action="ad_delete", payload=str(ad_id)))
        await session.commit()
    await cb.message.answer("🗑 Advert deleted.")
    await cb.answer()
