from aiogram.fsm.state import StatesGroup, State

class AddToken(StatesGroup):
    waiting_address = State()
    waiting_source = State()
    waiting_pool = State()

class CreateAd(StatesGroup):
    waiting_text = State()
    waiting_button_text = State()
    waiting_button_url = State()
