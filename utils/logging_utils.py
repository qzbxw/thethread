from aiogram import Bot
import traceback
import logging
import asyncio
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import Config

main_bot = None
_admin_bot: Bot | None = None

def _get_admin_bot() -> Bot | None:
    global _admin_bot
    if _admin_bot is None and Config.ADMIN_BOT_TOKEN:
        try:
            # Use default HTML for normal messages, but we'll explicitly set parse_mode=None for logs.
            _admin_bot = Bot(token=Config.ADMIN_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        except Exception:
            _admin_bot = Bot(token=Config.ADMIN_BOT_TOKEN)
    return _admin_bot

def set_main_bot(bot: Bot):
    global main_bot
    main_bot = bot

class _AdminLogHandler(logging.Handler):
    def __init__(self, level=logging.WARNING):
        super().__init__(level=level)

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            asyncio.get_event_loop().create_task(send_log_to_admins(f"[log] {record.levelname}: {msg}"))
        except Exception as e:
            logging.warning(f"_AdminLogHandler.emit failed: {e}")

def setup_logging_bridge(level=logging.WARNING):
    root = logging.getLogger()
    if not any(isinstance(h, _AdminLogHandler) for h in root.handlers):
        handler = _AdminLogHandler(level=level)
        formatter = logging.Formatter("%(asctime)s %(name)s: %(message)s")
        handler.setFormatter(formatter)
        root.addHandler(handler)

async def send_log_to_admins(text: str):
    admin_bot = _get_admin_bot()
    # Ensure arbitrary log text doesn't break Telegram parsing by disabling parse mode.
    # Also trim extremely long logs to a reasonable size.
    MAX_LEN = 3500
    safe_text = text if len(text) <= MAX_LEN else (text[:MAX_LEN] + "\n…(truncated)")
    if admin_bot:
        if not Config.ADMIN_IDS:
            logging.warning("[logging_utils] ADMIN_IDS пуст — некуда отправлять логи админ-ботом.")
        for admin_id in Config.ADMIN_IDS:
            try:
                await admin_bot.send_message(admin_id, safe_text, parse_mode=None)
            except Exception as e:
                logging.error(f"Failed to send log via admin bot to {admin_id}: {e}")
        return
    if main_bot:
        if not Config.ADMIN_IDS:
            logging.warning("[logging_utils] ADMIN_IDS пуст — некуда отправлять логи основным ботом.")
        for admin_id in Config.ADMIN_IDS:
            try:
                await main_bot.send_message(admin_id, safe_text, parse_mode=None)
            except Exception as e:
                logging.error(f"Failed to send log via main bot to {admin_id}: {e}")
    else:
        if not Config.ADMIN_BOT_TOKEN:
            logging.warning("[logging_utils] ADMIN_BOT_TOKEN не задан — админ-бот для логов не активен.")
        logging.warning("[logging_utils] main_bot не установлен — логи не могут быть отправлены.")

async def log_new_user(username: str, user_id: int):
    await send_log_to_admins(f"New user: {username} (ID: {user_id})")

async def log_payment(username: str, amount_crystals: int, amount_usd: float):
    await send_log_to_admins(f"✅ Successful payment: {username} bought {amount_crystals} for ${amount_usd}")

async def log_error(error: str):
    await send_log_to_admins(f"❌ Error: {error}")

async def log_exception(exc: Exception):
    tb = "\n".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    await send_log_to_admins(f"❌ Exception:\n<pre>{tb}</pre>")
