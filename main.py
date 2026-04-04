import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import settings
from models.db_models import init_db, AsyncSessionLocal
from middleware.auth import AuthMiddleware
from middleware.rate_limiter import RateLimiterMiddleware
from middleware.anti_cheat import AntiCheatMiddleware
from handlers import (
    start_handler,
    task_handler,
    leaderboard_handler,
    achievement_handler,
    admin_handler,
    group_handler,
)
from scheduler.scheduler import create_scheduler

async def main():
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    await init_db()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher()

    # Middleware — order matters: auth first, then rate limiter, then anti-cheat
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())
    dp.message.middleware(RateLimiterMiddleware())
    dp.message.middleware(AntiCheatMiddleware())

    # Routers
    dp.include_router(start_handler.router)
    dp.include_router(task_handler.router)
    dp.include_router(leaderboard_handler.router)
    dp.include_router(achievement_handler.router)
    dp.include_router(admin_handler.router)
    dp.include_router(group_handler.router)

    # Global error handler — catches any unhandled exception from any handler
    @dp.errors()
    async def global_error_handler(event, exception):
        logging.error(f"Unhandled exception: {exception}", exc_info=True)
        try:
            if hasattr(event, "message") and event.message:
                await event.message.answer("Something went wrong. Please try again.")
            elif hasattr(event, "callback_query") and event.callback_query:
                await event.callback_query.answer("Something went wrong.", show_alert=True)
        except Exception:
            pass
        # Do NOT re-raise — prevents the update from being retried infinitely

    scheduler = create_scheduler(bot, AsyncSessionLocal)
    scheduler.start()
    logging.info("Bot started. Polling...")

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())