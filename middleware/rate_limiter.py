from aiogram.dispatcher.middlewares.base import BaseMiddleware
from cache.ttl_cache import rate_limit_cache
from config import settings

class RateLimiterMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        message = getattr(event, "message", None)
        if not message:
            return await handler(event, data)

        # Only apply to task submission messages, not commands
        if message.text and message.text.startswith(("/", "/start", "/leaderboard")):
            return await handler(event, data)

        user = data.get("user")
        if not user:
            return await handler(event, data)
        user_id = user.id
        group_id = message.chat.id

        key = f"rl:{user_id}:{group_id}"
        if rate_limit_cache.get(key):
            await message.answer("Please wait before submitting again.")
            return

        result = await handler(event, data)
        rate_limit_cache.set(key, True, ttl=settings.rate_limit_seconds)
        return result