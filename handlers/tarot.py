from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatAction, ParseMode
from aiogram.exceptions import TelegramBadRequest
from datetime import datetime, timedelta
import logging

from models.database import db
from utils.tarot_utils import draw_cards
from utils.gemini_utils import generate_ai_response
from config import Config
from utils.ui import (
    incognito_preset_kb,
    incognito_preset_kb_disabled,
    main_menu_kb,
    end_dialog_kb,
    confirm_spend_kb,
)
from utils.ui import set_active_kb

router = Router()

class TarotStates(StatesGroup):
    ask_question = State()
    selecting_options = State()
    in_dialog = State()

@router.callback_query(F.data.in_( ["tarot_free", "tarot_quick", "tarot_deep"]))
async def start_tarot(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("Готовлю расклад")
    user_id = callback.from_user.id
    action = callback.data
    
    user = await db.get_user(user_id)
    if not user:
        await callback.message.edit_text("Пользователь не найден.")
        return

    if action == "tarot_free":
        num_cards = 1
        cost = 0
    elif action == "tarot_quick":
        num_cards = 3
        cost = Config.TAROT_QUICK_COST
    elif action == "tarot_deep":
        num_cards = 10
        cost = Config.TAROT_DEEP_COST

    if cost > 0:
        balance = user['balance_crystals']
        if balance < cost:
            shortage = cost - balance
            text = (
                f"Выбран расклад: {'Быстрый' if action=='tarot_quick' else 'Глубокий'}\n\n"
                f"Стоимость: <b>{cost}</b> 💎\n"
                f"Твой баланс: <b>{balance}</b> 💎\n"
                f"Не хватает: <b>{shortage}</b> 💎\n\n"
                "Пополни баланс и вернись к выбору расклада."
            )
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="💎 Пополнить", callback_data="buy_crystals")],
                [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")],
            ])
            await callback.message.edit_text(text, reply_markup=kb)
            await set_active_kb(callback.message)
            return
        else:
            text = (
                f"Выбран расклад: {'Быстрый' if action=='tarot_quick' else 'Глубокий'}\n\n"
                f"Стоимость: <b>{cost}</b> 💎\n"
                f"Твой баланс: <b>{balance}</b> 💎\n\n"
                "После подтверждения я попрошу тебя сформулировать вопрос."
            )
            await state.set_state(TarotStates.selecting_options)
            await state.update_data(selected_action=action, num_cards=num_cards, cost=cost, message_history=[], user_question="", incognito=False, last_ai_message_id=None, last_activity=datetime.now().isoformat())
            await callback.message.edit_text(text, reply_markup=confirm_spend_kb(action, cost))
            await set_active_kb(callback.message)
            return

    await state.set_state(TarotStates.ask_question)
    await state.update_data(selected_action=action, num_cards=num_cards, cost=cost, message_history=[], user_question="", incognito=False, last_ai_message_id=None, last_activity=datetime.now().isoformat())
    await callback.message.edit_text(
        "О чём хочешь спросить? Напиши свой вопрос одним сообщением.",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]])
    )
    await set_active_kb(callback.message)

@router.callback_query(F.data.startswith("confirm_spend:"))
async def confirm_spend(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("Подтверждено")
    _, action = callback.data.split(":", 1)
    data = await state.get_data()
    if not data or data.get('selected_action') != action:
        await callback.answer("Сессия устарела", show_alert=True)
        return
    await state.set_state(TarotStates.ask_question)
    await callback.message.edit_text(
        "О чём хочешь спросить? Напиши свой вопрос одним сообщением.",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]])
    )

@router.message(TarotStates.ask_question, F.text)
async def receive_question(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user_display_name = getattr(message.from_user, 'first_name', None) or getattr(message.from_user, 'full_name', None) or message.from_user.username
    user_text = message.text.strip()
    user = await db.get_user(user_id)
    if not user:
        await message.reply("Пользователь не найден.")
        await state.clear()
        return
    data = await state.get_data()
    action = data.get('selected_action')
    num_cards = data.get('num_cards', 1)
    cost = data.get('cost', 0)

    if action == "tarot_free":
        if user['last_free_card_ts'] and datetime.now() - user['last_free_card_ts'] < timedelta(hours=Config.FREE_CARD_COOLDOWN_HOURS):
            kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]])
            await message.reply("Карта Дня доступна раз в 24 часа.", reply_markup=kb)
            await state.clear()
            return
    if cost > 0 and user['balance_crystals'] < cost:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="💎 Купить кристаллы", callback_data="buy_crystals")],
            [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")],
        ])
        await message.reply(
            f"Недостаточно кристаллов. Нужно {cost} 💎, у тебя {user['balance_crystals']} 💎.",
            reply_markup=kb
        )
        await state.clear()
        return

    if cost > 0:
        await db.update_balance(user_id, -cost)
    if action == "tarot_free":
        await db.set_last_free_card(user_id)

    await state.update_data(user_question=user_text)

    cards = draw_cards(num_cards)
    card_names = cards

    preset_text = (
        f"Твой расклад: {', '.join(card_names)}\n\n"
        "Перед началом диалога можешь включить режим Инкогнито.\n"
        "В Инкогнито мы не сохраняем историю твоих сообщений — поможем здесь и сейчас, но восстановить сессию не сможем."
    )
    await state.set_state(TarotStates.selecting_options)
    await state.update_data(cards=card_names, last_activity=datetime.now().isoformat())
    preset_msg = await message.reply(preset_text, reply_markup=incognito_preset_kb(data.get('incognito', False)))
    await set_active_kb(preset_msg)
    await state.update_data(preset_message_id=preset_msg.message_id)

@router.callback_query(F.data == "toggle_incognito")
async def toggle_incognito(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data:
        await callback.answer()
        return
    incognito = not data.get('incognito', False)
    await state.update_data(incognito=incognito, last_activity=datetime.now().isoformat())
    text = (
        f"Твой расклад: {', '.join(data.get('cards', []))}\n\n"
        + ("Инкогнито включен. Твоя история не сохраняется." if incognito else "Инкогнито выключен. История диалога используется в рамках сессии.")
    )
    await callback.answer("Инкогнито: " + ("включён" if incognito else "выключен"))
    await callback.message.edit_text(text, reply_markup=incognito_preset_kb(incognito))
    await set_active_kb(callback.message)

@router.callback_query(F.data == "proceed_dialog")
async def proceed_dialog(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data:
        await callback.answer()
        return
    await state.set_state(TarotStates.in_dialog)
    await state.update_data(last_activity=datetime.now().isoformat())
    user_display_name = getattr(callback.from_user, 'first_name', None) or getattr(callback.from_user, 'full_name', None) or callback.from_user.username
    cards = data.get('cards', [])
    question = data.get('user_question', '')
    incognito = data.get('incognito', False)
    history = [] if incognito else data.get('message_history', [])
    await callback.message.edit_reply_markup(reply_markup=incognito_preset_kb_disabled(incognito))
    await callback.message.bot.send_chat_action(chat_id=callback.message.chat.id, action=ChatAction.TYPING)
    sent = await callback.message.answer("Готовлю ответ…")
    ai_response = generate_ai_response(user_display_name, cards, question, history)
    try:
        await sent.edit_text(ai_response, reply_markup=end_dialog_kb(), parse_mode=ParseMode.MARKDOWN)
    except Exception:
        sent = await callback.message.answer(ai_response, reply_markup=end_dialog_kb(), parse_mode=ParseMode.MARKDOWN)
    await set_active_kb(sent)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e).lower():
            logging.warning(f"Failed to clear reply markup in proceed_dialog: {e}")
    except Exception as e:
        logging.warning(f"Failed to clear reply markup in proceed_dialog: {e}")
    await state.update_data()

@router.message(TarotStates.in_dialog, F.text)
async def handle_dialog(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user_display_name = message.from_user.username or (message.from_user.full_name if hasattr(message.from_user, 'full_name') else None)
    user_text = message.text
    
    data = await state.get_data()
    cards = data.get('cards', [])
    history = data.get('message_history', [])
    incognito = data.get('incognito', False)
    last_activity_iso = data.get('last_activity')
    now = datetime.now()
    if last_activity_iso:
        try:
            last_activity = datetime.fromisoformat(last_activity_iso)
            if now - last_activity > timedelta(minutes=Config.SESSION_TIMEOUT_MINUTES):
                await state.clear()
                await message.reply("Сессия истекла. Начни заново, когда захочешь.")
                return
        except Exception as e:
            logging.debug(f"Failed to parse last_activity timestamp or state handling error: {e}")
    
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
    
    if not data.get('user_question'):
        await state.update_data(user_question=user_text)
        ai_response = generate_ai_response(user_display_name, cards, user_text)
    else:
        if incognito:
            ai_response = generate_ai_response(user_display_name, cards, data['user_question'], [])
        else:
            history.append({"role": "user", "content": user_text})
            ai_response = generate_ai_response(user_display_name, cards, data['user_question'], history)
            history.append({"role": "assistant", "content": ai_response})
            await state.update_data(message_history=history)
    
    placeholder = await message.answer("Готовлю ответ…")
    try:
        await placeholder.edit_text(ai_response, reply_markup=end_dialog_kb(), parse_mode=ParseMode.MARKDOWN)
        sent = placeholder
    except Exception:
        sent = await message.answer(ai_response, reply_markup=end_dialog_kb(), parse_mode=ParseMode.MARKDOWN)
    await set_active_kb(sent)
    await state.update_data(last_activity=now.isoformat())

@router.message(TarotStates.ask_question, ~F.text)
async def reject_non_text_in_ask(message: types.Message):
    await message.reply(
        "Напиши вопрос текстом — файлы и голосовые пока не поддерживаю.",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]])
    )

@router.message(TarotStates.in_dialog, ~F.text)
async def reject_non_text_in_dialog(message: types.Message):
    await message.reply(
        "Напиши текстом — так проще разобраться.",
        reply_markup=end_dialog_kb()
    )

@router.message(Command("end"))
async def end_dialog(message: types.Message, state: FSMContext):
    await state.clear()
    user = await db.get_user(message.from_user.id)
    balance = user['balance_crystals'] if user else None
    free_available = True
    if user and user['last_free_card_ts']:
        try:
            last_ts = user['last_free_card_ts']
            free_available = datetime.now() - last_ts >= timedelta(hours=Config.FREE_CARD_COOLDOWN_HOURS)
        except Exception:
            free_available = True
    sent = await message.reply(
        "Диалог завершён. Удачи! 👋", 
        reply_markup=main_menu_kb(balance=balance, free_available=free_available)
    )
    await set_active_kb(sent)

@router.callback_query(F.data == "end_dialog")
async def end_dialog_cb(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("Диалог завершён")
    await state.clear()
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
        "Диалог завершён. Удачи! 👋", 
        reply_markup=main_menu_kb(balance=balance, free_available=free_available)
    )
    await set_active_kb(callback.message)

@router.callback_query(F.data == "back_to_main")
async def back_to_main_cb(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("Открываю меню")
    await state.clear()
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
        "Главное меню\n\n"
        "Что дальше?",
        reply_markup=main_menu_kb(balance=balance, free_available=free_available)
    )
    await set_active_kb(callback.message)

def register_tarot_handler(dp):
    dp.include_router(router)
