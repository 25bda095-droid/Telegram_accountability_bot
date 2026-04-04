from datetime import date as date_type
from sqlalchemy import select
from models.db_models import LeaderboardSnapshot
from .base_repo import BaseRepo

class SnapshotRepo(BaseRepo):
    async def save_snapshot(self, group_id: int, date: date_type, rankings: list[dict]):
        snapshots = [
            LeaderboardSnapshot(
                group_id=group_id,
                snapshot_date=date,
                user_id=entry["user_id"],
                rank=entry["rank"],
                points=entry["points"],
                streak=entry["streak"]
            )
            for entry in rankings
        ]
        self.session.add_all(snapshots)
        await self.session.flush()

    async def get_snapshot(self, group_id: int, date: date_type) -> list[LeaderboardSnapshot]:
        result = await self.session.execute(
            select(LeaderboardSnapshot)
            .where(
                LeaderboardSnapshot.group_id == group_id,
                LeaderboardSnapshot.snapshot_date == date
            )
            .order_by(LeaderboardSnapshot.rank.asc())
        )
        return result.scalars().all()

    async def get_user_best_rank(self, user_id: int, group_id: int) -> int | None:
        result = await self.session.execute(
            select(LeaderboardSnapshot.rank)
            .where(
                LeaderboardSnapshot.user_id == user_id,
                LeaderboardSnapshot.group_id == group_id
            )
            .order_by(LeaderboardSnapshot.rank.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()