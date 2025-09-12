import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import Config
from models.database import db
from utils.logging_utils import main_bot as MAIN_BOT

logging.basicConfig(level=logging.INFO)

# Define router at import time, but do not create Bot/Dispatcher here.
router = Router()

def is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS

def admin_menu_kb() -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [types.InlineKeyboardButton(text="💎 Начислить кристаллы", callback_data="admin_grant")],
        [types.InlineKeyboardButton(text="🧭 Найти пользователя", callback_data="admin_find")],
        [types.InlineKeyboardButton(text="📣 Рассылка", callback_data="admin_broadcast")],
    ])

class AdminStates(StatesGroup):
    grant_user_id = State()
    grant_amount = State()
    find_query = State()
    broadcast_text = State()
    broadcast_confirm = State()

@router.message(Command("start"))
async def admin_start(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.reply("Доступ запрещен.")
        return
    text = (
        "Thread Admin Bot\n\n"
        "Выберите действие:"
    )
    await message.reply(text, reply_markup=admin_menu_kb())

@router.callback_query(F.data == "admin_stats")
async def admin_stats_cb(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    async with db.pool.acquire() as conn:
        users_count = await conn.fetchval("SELECT COUNT(*) FROM users")
        transactions = await conn.fetch("SELECT SUM(amount_usd) as total_usd, SUM(amount_crystals) as total_crystals FROM transactions")
        total_usd = transactions[0]['total_usd'] or 0
        total_crystals = transactions[0]['total_crystals'] or 0
    text = (
        f"<b>Статистика</b>\n\n"
        f"Пользователей: {users_count}\n"
        f"Доход: ${total_usd}\n"
        f"Кристаллов продано: {total_crystals}"
    )
    await callback.message.edit_text(text, reply_markup=admin_menu_kb())

@router.callback_query(F.data == "admin_grant")
async def admin_grant_start(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.grant_user_id)
    await callback.message.edit_text("Введи <b>user_id</b> пользователя, которому начислить кристаллы:\n\n/cancel — отмена")

@router.message(AdminStates.grant_user_id)
async def admin_grant_user_id(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.reply("Доступ запрещен.")
        return
    if message.text and message.text.strip().casefold() == "/cancel":
        await state.clear()
        await message.reply("Отменено.", reply_markup=admin_menu_kb())
        return
    if not message.text.isdigit():
        await message.reply("Некорректный user_id. Введи число.")
        return
    await state.update_data(target_user_id=int(message.text))
    await state.set_state(AdminStates.grant_amount)
    await message.reply("Сколько 💎 начислить? Введи число:")

@router.message(AdminStates.grant_amount)
async def admin_grant_amount(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.reply("Доступ запрещен.")
        return
    if message.text and message.text.strip().casefold() == "/cancel":
        await state.clear()
        await message.reply("Отменено.", reply_markup=admin_menu_kb())
        return
    try:
        amount = int(message.text)
    except ValueError:
        await message.reply("Некорректная сумма. Введи число.")
        return
    data = await state.get_data()
    user_id = data.get("target_user_id")
    await db.update_balance(user_id, amount)
    await state.clear()
    await message.reply(f"Начислено {amount} 💎 пользователю {user_id}", reply_markup=admin_menu_kb())

@router.callback_query(F.data == "admin_find")
async def admin_find_start(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.find_query)
    await callback.message.edit_text("Введи <b>user_id</b> или <b>username</b> для поиска:\n\n/cancel — отмена")

@router.message(AdminStates.find_query)
async def admin_find_query(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.reply("Доступ запрещен.")
        return
    if message.text and message.text.strip().casefold() == "/cancel":
        await state.clear()
        await message.reply("Отменено.", reply_markup=admin_menu_kb())
        return
    query = message.text.strip()
    async with db.pool.acquire() as conn:
        if query.isdigit():
            user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", int(query))
        else:
            user = await conn.fetchrow("SELECT * FROM users WHERE username = $1", query)
        if user:
            transactions = await conn.fetch("SELECT * FROM transactions WHERE user_id = $1 ORDER BY created_at DESC LIMIT 5", user['user_id'])
            text = (
                f"Пользователь: {user['username']} (ID: {user['user_id']})\n"
                f"Баланс: {user['balance_crystals']} 💎\n"
                f"Последние транзакции:\n"
            )
            for t in transactions:
                text += f"- {t['amount_usd']}$ for {t['amount_crystals']} 💎\n"
        else:
            text = "Пользователь не найден."
    await state.clear()
    await message.reply(text, reply_markup=admin_menu_kb())

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.broadcast_text)
    await callback.message.edit_text("Введи текст рассылки:\n\n/cancel — отмена")

@router.message(AdminStates.broadcast_text)
async def admin_broadcast_text(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.reply("Доступ запрещен.")
        return
    if message.text and message.text.strip().casefold() == "/cancel":
        await state.clear()
        await message.reply("Отменено.", reply_markup=admin_menu_kb())
        return
    text = (message.text or "").strip()
    if not text:
        await message.reply("Текст пуст. Введи сообщение для рассылки.")
        return
    await state.update_data(broadcast_text=text)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Разослать", callback_data="broadcast_confirm")],
        [types.InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast_cancel")],
    ])
    await message.reply(f"Подтверди рассылку:\n\n{text}", reply_markup=kb)

@router.callback_query(F.data == "broadcast_cancel")
async def admin_broadcast_cancel(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text("Отменено.", reply_markup=admin_menu_kb())

@router.callback_query(F.data == "broadcast_confirm")
async def admin_broadcast_confirm(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    data = await state.get_data()
    text = (data.get("broadcast_text") or "").strip()
    if not text:
        await callback.answer("Текст пуст или сессия устарела. Начни заново.", show_alert=True)
        return
    await state.clear()
    async with db.pool.acquire() as conn:
        users = await conn.fetch("SELECT user_id FROM users")

    # Prefer reusing the main bot instance started in render_entry (so session is shared)
    temp_bot: Bot | None = None
    bot_to_use: Bot | None = MAIN_BOT
    if bot_to_use is None:
        # Fallback: create a temporary main bot client and make sure to close session afterwards
        temp_bot = Bot(token=Config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        bot_to_use = temp_bot

    # Telegram text limit is ~4096; chunk if needed
    def _chunks(s: str, n: int = 4000):
        for i in range(0, len(s), n):
            yield s[i:i+n]

    sent = 0
    for user in users:
        try:
            for part in _chunks(text):
                await bot_to_use.send_message(user['user_id'], part)
            sent += 1
        except Exception as e:
            logging.error(f"Failed to send to {user['user_id']}: {e}")
    try:
        await callback.message.edit_text(f"Рассылка завершена. Отправлено: {sent}", reply_markup=admin_menu_kb())
    finally:
        if temp_bot is not None:
            # Properly close temporary client session to avoid 'Unclosed client session'
            try:
                await temp_bot.session.close()
            except Exception:
                pass

@router.message(Command("menu"))
async def admin_menu_cmd(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.reply("Доступ запрещен.")
        return
    await message.reply("Главное меню", reply_markup=admin_menu_kb())

@router.message(Command("cancel"))
@router.message(F.text.casefold() == "/cancel")
async def admin_cancel(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.reply("Доступ запрещен.")
        return
    await state.clear()
    await message.reply("Отменено.", reply_markup=admin_menu_kb())

@router.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if message.from_user.id not in Config.ADMIN_IDS:
        await message.reply("Доступ запрещен.")
        return
    
    async with db.pool.acquire() as conn:
        users_count = await conn.fetchval("SELECT COUNT(*) FROM users")
        transactions = await conn.fetch("SELECT SUM(amount_usd) as total_usd, SUM(amount_crystals) as total_crystals FROM transactions")
        total_usd = transactions[0]['total_usd'] or 0
        total_crystals = transactions[0]['total_crystals'] or 0
    
    text = f"Статистика:\n" \
           f"Пользователей: {users_count}\n" \
           f"Доход: ${total_usd}\n" \
           f"Кристаллов продано: {total_crystals}"
    
    await message.reply(text)

@router.message(Command("grant_crystals"))
async def cmd_grant_crystals(message: types.Message):
    if message.from_user.id not in Config.ADMIN_IDS:
        await message.reply("Доступ запрещен.")
        return
    
    args = message.text.split()
    if len(args) != 3:
        await message.reply("Использование: /grant_crystals [user_id] [amount]")
        return
    
    try:
        user_id = int(args[1])
        amount = int(args[2])
    except ValueError:
        await message.reply("Неверные аргументы.")
        return
    
    await db.update_balance(user_id, amount)
    await message.reply(f"Начислено {amount} 💎 пользователю {user_id}")

@router.message(Command("find_user"))
async def cmd_find_user(message: types.Message):
    if message.from_user.id not in Config.ADMIN_IDS:
        await message.reply("Доступ запрещен.")
        return
    
    args = message.text.split()
    if len(args) != 2:
        await message.reply("Использование: /find_user [user_id или username]")
        return
    
    query = args[1]
    async with db.pool.acquire() as conn:
        if query.isdigit():
            user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", int(query))
        else:
            user = await conn.fetchrow("SELECT * FROM users WHERE username = $1", query)
        
        if user:
            transactions = await conn.fetch("SELECT * FROM transactions WHERE user_id = $1 ORDER BY created_at DESC LIMIT 5", user['user_id'])
            text = f"Пользователь: {user['username']} (ID: {user['user_id']})\n" \
                   f"Баланс: {user['balance_crystals']} 💎\n" \
                   f"Последние транзакции:\n"
            for t in transactions:
                text += f"- {t['amount_usd']}$ for {t['amount_crystals']} 💎\n"
            await message.reply(text)
        else:
            await message.reply("Пользователь не найден.")

@router.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message):
    if message.from_user.id not in Config.ADMIN_IDS:
        await message.reply("Доступ запрещен.")
        return
    
    broadcast_text = message.text.replace("/broadcast", "").strip()
    if not broadcast_text:
        await message.reply("Укажите сообщение для рассылки.")
        return
    
    async with db.pool.acquire() as conn:
        users = await conn.fetch("SELECT user_id FROM users")

    main_bot = Bot(token=Config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    for user in users:
        try:
            await main_bot.send_message(user['user_id'], broadcast_text)
        except Exception as e:
            logging.error(f"Failed to send to {user['user_id']}: {e}")
    
    await message.reply("Рассылка завершена.")

def get_admin_router() -> Router:
    """Expose admin router for reuse by other entrypoints."""
    return router

async def main():
    await db.connect()
    # Ensure tables exist in case admin worker starts before main service
    try:
        await db.create_tables()
    except Exception:
        pass
    # Create bot/dispatcher only when running this module standalone
    bot = Bot(token=Config.ADMIN_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    try:
        await dp.start_polling(bot)
    finally:
        try:
            await db.disconnect()
        except Exception:
            pass

if __name__ == "__main__":
    asyncio.run(main())
