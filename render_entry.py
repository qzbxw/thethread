import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import Config
from models.database import db
from handlers import register_handlers
from utils.logging_utils import set_main_bot, setup_logging_bridge
from handlers.stripe_webhook import start_webhook_server
from admin_bot import get_admin_router

logging.basicConfig(level=logging.INFO)

async def run():
    logging.info(f"DATABASE_URL: {Config.DATABASE_URL}")
    bot = Bot(token=Config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    set_main_bot(bot)
    setup_logging_bridge(level=logging.WARNING)

    await db.connect()
    await db.create_tables()

    asyncio.create_task(start_webhook_server())

    # Register all bot handlers so updates are processed
    register_handlers(dp)

    # Optionally start admin bot in the same process if token provided
    admin_task = None
    if Config.ADMIN_BOT_TOKEN:
        admin_bot = Bot(token=Config.ADMIN_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        admin_dp = Dispatcher()
        admin_dp.include_router(get_admin_router())
        admin_task = asyncio.create_task(admin_dp.start_polling(admin_bot))

    try:
        if admin_task:
            await asyncio.gather(
                dp.start_polling(bot),
                admin_task,
            )
        else:
            await dp.start_polling(bot)
    finally:
        # Graceful shutdown: close DB pool to free connections
        try:
            await db.disconnect()
        except Exception:
            pass

if __name__ == "__main__":
    asyncio.run(run())
