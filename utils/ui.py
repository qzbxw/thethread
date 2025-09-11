from aiogram import types
from models.database import db
from config import Config
import logging

def _noop_btn(text: str) -> types.InlineKeyboardButton:
    return types.InlineKeyboardButton(text=text, callback_data="noop")

def main_menu_kb(balance: int | None = None, free_available: bool | None = None) -> types.InlineKeyboardMarkup:
    free_text = "🃏 Карта Дня (бесплатно)" if (free_available is None or free_available) else "🃏 Карта Дня — завтра"
    free_button = types.InlineKeyboardButton(text=free_text, callback_data="tarot_free" if (free_available is None or free_available) else "noop_free_cd")

    keyboard = [
        [free_button],
        [types.InlineKeyboardButton(text=f"⚡️ Быстрый расклад ({Config.TAROT_QUICK_COST} 💎)", callback_data="tarot_quick")],
        [types.InlineKeyboardButton(text=f"🔮 Глубокий анализ ({Config.TAROT_DEEP_COST} 💎)", callback_data="tarot_deep")],
        [types.InlineKeyboardButton(text="💼 Мой баланс", callback_data="balance")],
        [types.InlineKeyboardButton(text="💎 Купить кристаллы", callback_data="buy_crystals")],
        [types.InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")],
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)


def crystals_menu_kb() -> types.InlineKeyboardMarkup:
    def _fmt(cents: int) -> str:
        return f"${cents/100:.2f}"
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=f"Пробник — {Config.CRYSTALS_PROBE} 💎 ({_fmt(Config.PRICE_PROBE_CENTS)})", callback_data="buy_probe")],
        [types.InlineKeyboardButton(text=f"Стандарт — {Config.CRYSTALS_STANDARD} 💎 ({_fmt(Config.PRICE_STANDARD_CENTS)})", callback_data="buy_standard")],
        [types.InlineKeyboardButton(text=f"Премиум — {Config.CRYSTALS_PREMIUM} 💎 ({_fmt(Config.PRICE_PREMIUM_CENTS)})", callback_data="buy_premium")],
        [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")],
    ])


def incognito_preset_kb(incognito_enabled: bool) -> types.InlineKeyboardMarkup:
    toggle_text = "🔓 Выключить Инкогнито" if incognito_enabled else "🤫 Включить Инкогнито"
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=toggle_text, callback_data="toggle_incognito")],
        [types.InlineKeyboardButton(text="Продолжить ➡️", callback_data="proceed_dialog")],
        [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")],
    ])


def incognito_preset_kb_disabled(incognito_enabled: bool) -> types.InlineKeyboardMarkup:
    """Disabled version while processing to prevent double taps."""
    toggle_text = "🔓 Выключить Инкогнито" if incognito_enabled else "🤫 Включить Инкогнито"
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [_noop_btn(f"⏳ {toggle_text}")],
        [_noop_btn("⏳ Продолжение…")],
        [_noop_btn("⏳ Назад")],
    ])


def end_dialog_kb() -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🛑 Завершить диалог", callback_data="end_dialog")]
    ])


def confirm_spend_kb(action: str, cost: int) -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=f"✅ Подтвердить −{cost} 💎", callback_data=f"confirm_spend:{action}")],
        [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")],
    ])


def confirm_spend_kb_disabled(cost: int) -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [_noop_btn(f"⏳ Подтверждение −{cost} 💎…")],
        [_noop_btn("⏳ Назад")],
    ])


def help_menu_kb() -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="❓ Как это работает", callback_data="how_it_works")],
        [types.InlineKeyboardButton(text="🔐 Политика конфиденциальности", callback_data="privacy")],
        [types.InlineKeyboardButton(text="📜 Пользовательское соглашение", callback_data="terms")],
        [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")],
    ])


async def set_active_kb(message: types.Message):
    try:
        user_id = message.chat.id  
        prev_id = await db.get_active_message_id(user_id)
        if prev_id and prev_id != message.message_id:
            try:
                await message.bot.edit_message_reply_markup(chat_id=message.chat.id, message_id=prev_id, reply_markup=None)
            except Exception as e:
                logging.debug(f"Failed to clear previous inline keyboard for user {user_id}: {e}")
        await db.set_active_message_id(user_id, message.message_id)
    except Exception as e:
        logging.warning(f"set_active_kb failed for message {getattr(message, 'message_id', None)}: {e}")
