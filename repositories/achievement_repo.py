from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from models.db_models import Achievement
from .base_repo import BaseRepo

class AchievementRepo(BaseRepo):
    async def has_achievement(self, user_id: int, group_id: int, key: str) -> bool:
        result = await self.session.execute(
            select(Achievement)
            .where(
                Achievement.user_id == user_id,
                Achievement.group_id == group_id,
                Achievement.achievement_key == key
            )
        )
        return result.scalar_one_or_none() is not None

    async def award(self, user_id: int, group_id: int, key: str) -> Achievement | None:
        achievement = Achievement(
            user_id=user_id,
            group_id=group_id,
            achievement_key=key
        )
        self.session.add(achievement)
        try:
            await self.session.flush()
            return achievement
        except IntegrityError:
            await self.session.rollback()
            return None

    async def get_user_achievements(self, user_id: int, group_id: int) -> list[Achievement]:
        result = await self.session.execute(
            select(Achievement)
            .where(
                Achievement.user_id == user_id,
                Achievement.group_id == group_id
            )
            .order_by(Achievement.awarded_at.asc())
        )
        return result.scalars().all()