from datetime import datetime, timezone
from sqlalchemy import select, update, and_
from models.db_models import TaskSubmission
from .base_repo import BaseRepo

class TaskRepo(BaseRepo):
    async def create_submission(self, user_id, group_id, proof_text, proof_file_id, points, streak_day) -> TaskSubmission:
        submission = TaskSubmission(
            user_id=user_id,
            group_id=group_id,
            proof_text=proof_text,
            proof_file_id=proof_file_id,
            points_awarded=points,
            streak_day=streak_day
        )
        self.session.add(submission)
        await self.session.flush()
        return submission

    async def get_today_submission(self, user_id: int, group_id: int) -> TaskSubmission | None:
        today = datetime.now(timezone.utc).date()
        start = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
        end = datetime.combine(today, datetime.max.time(), tzinfo=timezone.utc)
        result = await self.session.execute(
            select(TaskSubmission)
            .where(
                TaskSubmission.user_id == user_id,
                TaskSubmission.group_id == group_id,
                TaskSubmission.submitted_at >= start,
                TaskSubmission.submitted_at <= end
            )
        )
        return result.scalar_one_or_none()

    async def count_today_submissions(self, group_id: int) -> int:
        today = datetime.now(timezone.utc).date()
        start = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
        end = datetime.combine(today, datetime.max.time(), tzinfo=timezone.utc)
        result = await self.session.execute(
            select(TaskSubmission)
            .where(
                TaskSubmission.group_id == group_id,
                TaskSubmission.submitted_at >= start,
                TaskSubmission.submitted_at <= end
            )
        )
        return result.scalars().all().__len__()

    async def get_user_submissions(self, user_id: int, group_id: int, limit: int = 30) -> list[TaskSubmission]:
        result = await self.session.execute(
            select(TaskSubmission)
            .where(
                TaskSubmission.user_id == user_id,
                TaskSubmission.group_id == group_id
            )
            .order_by(TaskSubmission.submitted_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def flag_submission(self, submission_id: int):
        await self.session.execute(
            update(TaskSubmission)
            .where(TaskSubmission.id == submission_id)
            .values(is_flagged=True)
        )