from aiogram import Dispatcher
from app.tg.handlers_setup import router as setup_router
from app.tg.handlers_tokens import router as tokens_router
from app.tg.handlers_ads import router as ads_router

def setup_dispatcher(dp: Dispatcher):
    dp.include_router(setup_router)
    dp.include_router(tokens_router)
    dp.include_router(ads_router)
