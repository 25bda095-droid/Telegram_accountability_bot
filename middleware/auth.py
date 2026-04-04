from aiogram.dispatcher.middlewares.base import BaseMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from models.db_models import AsyncSessionLocal
from repositories.user_repo import UserRepo

class AuthMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        async with AsyncSessionLocal() as session:
            data["session"] = session
            tg_user = data["event_from_user"]
            user_repo = UserRepo(session)
            user, _ = await user_repo.get_or_create(
                user_id=tg_user.id,
                username=tg_user.username or "",
                full_name=tg_user.full_name,
            )
            data["user"] = user
            if getattr(user, "is_banned", False):
                if hasattr(event, "message"):
                    await event.message.answer("You are not allowed to participate.")
                return
            result = await handler(event, data)
            await session.commit()
            return result
