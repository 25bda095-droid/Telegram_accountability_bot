from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from models.db_models import User
from .base_repo import BaseRepo

class UserRepo(BaseRepo):
    async def get_by_id(self, user_id: int) -> User | None:
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create(self, user_id: int, username: str, full_name: str) -> tuple[User, bool]:
        user = await self.get_by_id(user_id)
        if user:
            return user, False
        user = User(id=user_id, username=username, full_name=full_name)
        self.session.add(user)
        await self.session.flush()
        return user, True

    async def update_points(self, user_id: int, points: int):
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(total_points=User.total_points + points)
        )

    async def ban(self, user_id: int):
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(is_banned=True)
        )

    async def unban(self, user_id: int):
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(is_banned=False)
        )

    async def get_top_n(self, group_id: int, n: int = 10) -> list[User]:
        # group_id is not used in User table, but may be used in a join with TaskSubmission if needed.
        # For now, return top users by total_points.
        result = await self.session.execute(
            select(User).order_by(User.total_points.desc()).limit(n)
        )
        return result.scalars().all()