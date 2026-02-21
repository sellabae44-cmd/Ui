from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from app.tg.menus import ops_center_kb, tokens_kb, ads_kb, simple_back

router = Router()

@router.message(Command("start"))
async def start_cmd(message: Message):
    await message.answer("🛰️ SpyTON Ops Center\n\nUse /setup.", reply_markup=simple_back())

@router.message(Command("setup"))
async def setup_cmd(message: Message):
    await message.answer("🛰️ SpyTON Ops Center\nChoose a module:", reply_markup=ops_center_kb())

@router.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer("Commands:\n/setup - Open Ops Center\n")

@router.callback_query(F.data == "menu:home")
async def home(cb: CallbackQuery):
    await cb.message.edit_text("🛰️ SpyTON Ops Center\nChoose a module:", reply_markup=ops_center_kb())
    await cb.answer()

@router.callback_query(F.data == "menu:tokens")
async def menu_tokens(cb: CallbackQuery):
    await cb.message.edit_text("🔎 Track Tokens", reply_markup=tokens_kb())
    await cb.answer()

@router.callback_query(F.data == "menu:ads")
async def menu_ads(cb: CallbackQuery):
    await cb.message.edit_text("📢 Intel Ads", reply_markup=ads_kb())
    await cb.answer()

@router.callback_query(F.data.in_({"menu:style","menu:trending","menu:shield","menu:logs","menu:lang","menu:settings"}))
async def coming(cb: CallbackQuery):
    await cb.message.edit_text("🧩 Module wired; full build comes next.", reply_markup=simple_back())
    await cb.answer()
