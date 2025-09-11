from aiogram import Router, types, F
from models.database import db

router = Router()

@router.callback_query(F.data == "balance")
async def show_balance(callback: types.CallbackQuery):
    await callback.answer("Смотрю баланс")
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if user:
        balance = user['balance_crystals']
        text = f"Твой баланс: <b>{balance}</b> 💎"
    else:
        text = "Пользователь не найден."
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="💎 Купить кристаллы", callback_data="buy_crystals")],
        [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")],
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)

def register_balance_handler(dp):
    dp.include_router(router)
