import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import Config
from models.database import db
from handlers import register_handlers
from utils.logging_utils import set_main_bot
from handlers.stripe_webhook import start_webhook_server

logging.basicConfig(level=logging.INFO)

async def run():
    logging.info(f"DATABASE_URL: {Config.DATABASE_URL}")
    bot = Bot(token=Config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    set_main_bot(bot)

    await db.connect()
    await db.create_tables()

    asyncio.create_task(start_webhook_server())

    try:
        await dp.start_polling(bot)
    finally:
        # Graceful shutdown: close DB pool to free connections
        try:
            await db.disconnect()
        except Exception:
            pass

if __name__ == "__main__":
    asyncio.run(run())
