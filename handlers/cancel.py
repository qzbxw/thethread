from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta

from models.database import db
from utils.ui import main_menu_kb
from config import Config

router = Router()

@router.message(Command("cancel"))
@router.message(F.text.casefold() == "/cancel")
async def global_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    user = await db.get_user(message.from_user.id)
    balance = user['balance_crystals'] if user else 0
    free_available = True
    if user and user.get('last_free_card_ts'):
        try:
            delta = datetime.now() - user['last_free_card_ts']
            free_available = delta >= timedelta(hours=Config.FREE_CARD_COOLDOWN_HOURS)
        except Exception:
            free_available = True
    await message.reply(
        "Отменено. Открою меню:",
        reply_markup=main_menu_kb(balance=balance, free_available=free_available)
    )


def register_cancel_handler(dp):
    dp.include_router(router)
