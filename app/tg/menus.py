from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def ops_center_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔎 Track Tokens", callback_data="menu:tokens"),
         InlineKeyboardButton(text="🧩 Style Lab", callback_data="menu:style")],
        [InlineKeyboardButton(text="📢 Intel Ads", callback_data="menu:ads"),
         InlineKeyboardButton(text="⚡ Trending Boost", callback_data="menu:trending")],
        [InlineKeyboardButton(text="🛡️ Shield", callback_data="menu:shield"),
         InlineKeyboardButton(text="🧾 Logs", callback_data="menu:logs")],
        [InlineKeyboardButton(text="🌐 Language", callback_data="menu:lang"),
         InlineKeyboardButton(text="⚙️ Settings", callback_data="menu:settings")],
    ])

def tokens_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Token", callback_data="tokens:add"),
         InlineKeyboardButton(text="📋 View Tokens", callback_data="tokens:list")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="menu:home")],
    ])

def ads_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧾 Create Bot Advert", callback_data="ads:create"),
         InlineKeyboardButton(text="🧹 Remove Ads", callback_data="ads:toggle")],
        [InlineKeyboardButton(text="📋 View Adverts", callback_data="ads:list"),
         InlineKeyboardButton(text="⬅️ Back", callback_data="menu:home")],
    ])

def simple_back():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back", callback_data="menu:home")]])
