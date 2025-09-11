from aiogram import Router, types, F
from aiogram.filters import Command
from datetime import datetime, timedelta
from datetime import datetime, timedelta

from config import Config
from models.database import db
from utils.ui import main_menu_kb
from utils.ui import set_active_kb
from utils.logging_utils import log_new_user

router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username

    user = await db.get_user(user_id)
    if not user:
        await db.create_user(user_id, username)
        await log_new_user(username or "Unknown", user_id)

    user = await db.get_user(user_id)

    balance = user['balance_crystals'] if user else None
    free_available = True
    remaining_text = "доступна"
    if user and user['last_free_card_ts']:
        try:
            last_ts = user['last_free_card_ts']
            delta = datetime.now() - last_ts
            free_available = delta >= timedelta(hours=Config.FREE_CARD_COOLDOWN_HOURS)
            if not free_available:
                hours_left = max(0, int((timedelta(hours=Config.FREE_CARD_COOLDOWN_HOURS) - delta).total_seconds() // 3600))
                remaining_text = f"через ~{hours_left}ч"
        except Exception:
            free_available = True
            remaining_text = "доступна"

    text = (
        "Привет! 👋\n\n"
        "Я — Нить, помогаю разобраться в ситуациях через карты Таро. Никакой мистики, только размышления.\n\n"
        f"Баланс: <b>{balance if balance is not None else 0}</b> 💎\n"
        f"Карта дня: <b>{'доступна' if free_available else remaining_text}</b>\n\n"
        "Что выберешь?"
    )
    sent = await message.reply(text, reply_markup=main_menu_kb(balance=balance, free_available=free_available))
    await set_active_kb(sent)

@router.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    await callback.answer("Открываю меню")
    user = await db.get_user(callback.from_user.id)
    balance = user['balance_crystals'] if user else None
    free_available = True
    remaining_text = "доступна"
    if user and user['last_free_card_ts']:
        try:
            last_ts = user['last_free_card_ts']
            delta = datetime.now() - last_ts
            free_available = delta >= timedelta(hours=Config.FREE_CARD_COOLDOWN_HOURS)
            if not free_available:
                hours_left = max(0, int((timedelta(hours=Config.FREE_CARD_COOLDOWN_HOURS) - delta).total_seconds() // 3600))
                remaining_text = f"через ~{hours_left}ч"
        except Exception:
            free_available = True
            remaining_text = "доступна"
    text = (
        "Главное меню\n\n"
        f"Баланс: <b>{balance if balance is not None else 0}</b> 💎\n"
        f"Карта дня: <b>{'доступна' if free_available else remaining_text}</b>\n\n"
        "Что дальше?"
    )
    await callback.message.edit_text(text, reply_markup=main_menu_kb(balance=balance, free_available=free_available))
    await set_active_kb(callback.message)


@router.callback_query(lambda c: c.data in ("noop", "noop_free_cd"))
async def noop_cb(callback: types.CallbackQuery):
    if callback.data == "noop_free_cd":
        await callback.answer("Карта дня будет доступна завтра", show_alert=False)
    else:
        await callback.answer("Недоступно сейчас", show_alert=False)

def register_start_handler(dp):
    dp.include_router(router)
