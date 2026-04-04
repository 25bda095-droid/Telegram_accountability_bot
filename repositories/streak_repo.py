from datetime import date as date_type
from sqlalchemy import select, update
from models.db_models import Streak
from .base_repo import BaseRepo

class StreakRepo(BaseRepo):
    async def get_streak(self, user_id: int, group_id: int) -> Streak | None:
        result = await self.session.execute(
            select(Streak)
            .where(
                Streak.user_id == user_id,
                Streak.group_id == group_id
            )
        )
        return result.scalar_one_or_none()

    async def upsert_streak(self, user_id: int, group_id: int, new_streak: int, last_date: date_type) -> Streak:
        streak = await self.get_streak(user_id, group_id)
        if streak:
            streak.current_streak = new_streak
            if new_streak > streak.longest_streak:
                streak.longest_streak = new_streak
            streak.last_submission_date = last_date
        else:
            streak = Streak(
                user_id=user_id,
                group_id=group_id,
                current_streak=new_streak,
                longest_streak=new_streak,
                last_submission_date=last_date
            )
            self.session.add(streak)
        await self.session.flush()
        return streak

    async def reset_streak(self, user_id: int, group_id: int):
        await self.session.execute(
            update(Streak)
            .where(
                Streak.user_id == user_id,
                Streak.group_id == group_id
            )
            .values(current_streak=0)
        )