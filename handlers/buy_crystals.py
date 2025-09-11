from aiogram import Router, types, F
from datetime import datetime, timedelta
import stripe
import logging
import uuid

from utils.ui import set_active_kb
from utils.logging_utils import log_payment
from utils.stripe_utils import create_checkout_session
from utils.ui import crystals_menu_kb, main_menu_kb
from models.database import db
from config import Config

stripe.api_key = Config.STRIPE_SECRET_KEY

router = Router()

@router.callback_query(F.data == "buy_crystals")
async def buy_crystals_menu(callback: types.CallbackQuery):
    await callback.answer("Выбираем пакет")
    text = (
        "Пополнение кристаллов\n\n"
        "Выбери пакет, оплата через Stripe."
    )
    await callback.message.edit_text(text, reply_markup=crystals_menu_kb())

@router.callback_query(F.data.in_( ["buy_probe", "buy_standard", "buy_premium"]))
async def process_buy(callback: types.CallbackQuery):
    await callback.answer("Готовлю оплату")
    package = callback.data.split("_")[1] 
    user_id = callback.from_user.id
    
    try:
        checkout_url, crystals, session_id = create_checkout_session(
            user_id=user_id,
            package=package,
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
        )
        token = uuid.uuid4().hex[:24]
        await db.save_checkout_session(user_id=user_id, token=token, session_id=session_id)
        text = (
            f"Почти готово!\n\n"
            f"Оплати {crystals} 💎. После успешной оплаты кристаллы поступят автоматически."
        )
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="💳 Оплатить", url=checkout_url)],
            [types.InlineKeyboardButton(text="🔁 Обновить после оплаты", callback_data=f"verify_payment:{token}")],
            [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")],
        ])
        try:
            await callback.message.edit_text(text, reply_markup=kb)
            await set_active_kb(callback.message)
        except Exception as e:
            logging.warning(f"edit_text failed in process_buy: {e}")
            sent = await callback.message.answer(text, reply_markup=kb)
            await set_active_kb(sent)
    except Exception as e:
        logging.exception(f"process_buy failed: {e}")
        try:
            await callback.message.edit_text("Что-то пошло не так. Попробуй позже.")
        except Exception:
            await callback.message.answer("Что-то пошло не так. Попробуй позже.")


@router.callback_query(F.data.startswith("verify_payment:"))
async def verify_payment(callback: types.CallbackQuery):
    await callback.answer("Проверяю")
    token_or_id = callback.data.split(":", 1)[1]
    try:
        session_id = token_or_id
        if not session_id.startswith("cs_"):
            mapped = await db.get_session_id_by_token(token_or_id)
            if not mapped:
                await callback.answer("Сессия не найдена. Попробуй через пару секунд.", show_alert=False)
                return
            session_id = mapped
        session = stripe.checkout.Session.retrieve(session_id)
        if session.get('payment_status') == 'paid':
            user_id = int(session['metadata']['user_id'])
            chat_id = int(session['metadata'].get('chat_id', user_id))
            crystals = int(session['metadata']['crystals'])
            amount_usd = session.get('amount_total', 0) / 100
            payment_intent = session.get('payment_intent')
            if not await db.transaction_exists(payment_intent):
                await db.update_balance(user_id, crystals)
                await db.record_transaction(user_id, payment_intent, amount_usd, crystals)
            if not token_or_id.startswith("cs_"):
                try:
                    await db.delete_checkout_session(token_or_id)
                except Exception as e:
                    logging.warning(f"Failed to delete checkout session mapping for token {token_or_id}: {e}")
            user = await db.get_user(user_id)
            balance_now = user['balance_crystals'] if user else 0
            free_available = True
            if user and user['last_free_card_ts']:
                try:
                    delta = datetime.now() - user['last_free_card_ts']
                    free_available = delta >= timedelta(hours=Config.FREE_CARD_COOLDOWN_HOURS)
                except Exception:
                    free_available = True
            await callback.message.edit_text(
                (
                    "Платёж подтверждён ✅\n"
                    f"Баланс обновлён: <b>{balance_now}</b> 💎\n\n"
                    "Выбирай, что дальше:"
                ),
                reply_markup=main_menu_kb(balance=balance_now, free_available=free_available),
            )
            await set_active_kb(callback.message)
            try:
                username = user['username'] if user and user.get('username') else str(user_id)
                await log_payment(username, crystals, amount_usd)
            except Exception as e:
                logging.warning(f"Failed to log payment for user {user_id}: {e}")
        else:
            await callback.answer("Платёж ещё не подтверждён", show_alert=False)
    except Exception as e:
        logging.warning(f"verify_payment failed: {e}")
        await callback.answer("Не удалось проверить платёж", show_alert=False)

@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    await callback.answer("Открываю меню")
    user = await db.get_user(callback.from_user.id)
    balance = user['balance_crystals'] if user else None
    free_available = True
    if user and user['last_free_card_ts']:
        try:
            last_ts = user['last_free_card_ts']
            free_available = datetime.now() - last_ts >= timedelta(hours=Config.FREE_CARD_COOLDOWN_HOURS)
        except Exception:
            free_available = True
    await callback.message.edit_text(
        "Главное меню\n\nЧто дальше?",
        reply_markup=main_menu_kb(balance=balance, free_available=free_available)
    )
    await set_active_kb(callback.message)

def register_buy_crystals_handler(dp):
    dp.include_router(router)
