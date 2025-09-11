from aiogram import Router, types, F
from aiogram.filters import Command
from datetime import datetime, timedelta
from aiogram.exceptions import TelegramBadRequest

from utils.ui import set_active_kb
from utils.ui import main_menu_kb, help_menu_kb
from models.database import db
from config import Config

router = Router()

PRIVACY_TEXT = """
<b>Политика конфиденциальности</b>

Мы собираем и обрабатываем только минимально необходимые данные, чтобы сервис работал корректно:
• <b>Telegram ID</b> и <b>username</b> — для идентификации пользователя и отправки сообщений в Telegram.
• <b>Баланс кристаллов</b> и записи об оплате — чтобы начислять покупки и предотвращать повторное списание.

Что <b>не</b> делаем:
• не продаём и не передаём ваши данные третьим лицам;
• не запрашиваем доступ к контактам/файлам/геолокации;
• не храним историю переписки в режиме <b>Инкогнито</b>.

Инкогнито:
• при включении мы <b>не сохраняем</b> историю ваших сообщений в рамках текущей сессии;
• данные используются только для формирования ответа «здесь и сейчас» и стираются по таймауту сессии.

Безопасность:
• доступ к БД ограничен, применяются технические и организационные меры защиты;
• платёжные данные обрабатываются <b>Stripe</b> — мы не получаем номера карт.
"""

TERMS_TEXT = """
<b>Пользовательское соглашение</b>

Назначение сервиса:
• это инструмент, а <b>не</b> гадание и не предсказания будущего;
• ответы AI — это интерпретация метафор карт и гипотезы, а не факты и не медицинские/юридические рекомендации.

Ограничения и ответственность:
• решения принимаете вы; ответственность за последствия ваших действий несёте вы;
• при критических состояниях обращайтесь к соответствующим специалистам (психолог, врач, юрист и т.п.).

Оплаты и кристаллы:
• платные расклады оплачиваются кристаллами; начисление происходит автоматически после подтверждения платежа;
• при технических сбоях мы используем идемпотентность транзакций, чтобы избежать двойного списания.

Поведение в чате:
• уважайте других и себя — не отправляйте запрещённый контент;
• бот может ограничивать функциональность при нарушениях.
"""

HOW_IT_WORKS = (
    "<b>Как это работает</b>\n\n"
    "• Выбираешь расклад (бесплатный или платный)\n"
    "• Задаёшь вопрос — лучше коротко и по делу\n"
    "• Я тяну карты и объясняю, что они могут значить\n"
    "• Можешь спросить что-то ещё в диалоге\n\n"
    "<b>Инкогнито</b>: история не сохраняется в рамках сессии\n"
)

@router.callback_query(F.data == "help")
async def help_menu(callback: types.CallbackQuery):
    await callback.answer("Помощь")
    try:
        if (callback.message.text or callback.message.html_text) == HOW_IT_WORKS:
            return
        await callback.message.edit_text(HOW_IT_WORKS, reply_markup=help_menu_kb())
        await set_active_kb(callback.message)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            return
        raise

@router.callback_query(F.data == "how_it_works")
async def how_it_works(callback: types.CallbackQuery):
    await callback.answer("Как это работает")
    try:
        if (callback.message.text or callback.message.html_text) == HOW_IT_WORKS:
            return
        await callback.message.edit_text(HOW_IT_WORKS, reply_markup=help_menu_kb())
        await set_active_kb(callback.message)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            return
        raise

@router.callback_query(F.data == "privacy")
async def show_privacy(callback: types.CallbackQuery):
    await callback.answer("Открываю")
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]])
    await callback.message.edit_text(PRIVACY_TEXT, reply_markup=kb)
    await set_active_kb(callback.message)

@router.callback_query(F.data == "terms")
async def show_terms(callback: types.CallbackQuery):
    await callback.answer("Открываю")
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]])
    await callback.message.edit_text(TERMS_TEXT, reply_markup=kb)
    await set_active_kb(callback.message)

@router.message(Command("privacy"))
async def cmd_privacy(message: types.Message):
    await message.reply(PRIVACY_TEXT, reply_markup=main_menu_kb())

@router.message(Command("terms"))
async def cmd_terms(message: types.Message):
    await message.reply(TERMS_TEXT, reply_markup=main_menu_kb())

def register_policies_handler(dp):
    dp.include_router(router)
