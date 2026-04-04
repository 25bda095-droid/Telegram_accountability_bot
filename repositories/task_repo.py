from datetime import datetime, timezone, date as date_type
from sqlalchemy import select, update, and_
from models.db_models import TaskSubmission, UserDailyTask, SkipRecord
from .base_repo import BaseRepo


# ─────────────────────────────────────
# Legacy repo (kept for backward compat)
# ─────────────────────────────────────

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
        return len(result.scalars().all())

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


# ─────────────────────────────────────
# NEW: Named daily task repo (1–6 slots)
# ─────────────────────────────────────

class DailyTaskRepo(BaseRepo):
    """CRUD for UserDailyTask — the per-day named task slots."""

    async def get_today_tasks(self, user_id: int, group_id: int) -> list[UserDailyTask]:
        """Return all tasks the user set today for this group, ordered by slot."""
        today = datetime.now(timezone.utc).date()
        result = await self.session.execute(
            select(UserDailyTask)
            .where(
                UserDailyTask.user_id == user_id,
                UserDailyTask.group_id == group_id,
                UserDailyTask.date == today,
            )
            .order_by(UserDailyTask.slot)
        )
        return list(result.scalars().all())

    async def get_task_slot(
        self, user_id: int, group_id: int, slot: int
    ) -> UserDailyTask | None:
        """Return a specific slot for today, or None if not set."""
        today = datetime.now(timezone.utc).date()
        result = await self.session.execute(
            select(UserDailyTask)
            .where(
                UserDailyTask.user_id == user_id,
                UserDailyTask.group_id == group_id,
                UserDailyTask.date == today,
                UserDailyTask.slot == slot,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_task_slot(
        self, user_id: int, group_id: int, slot: int, task_name: str
    ) -> UserDailyTask:
        """Create or update a task slot for today."""
        today = datetime.now(timezone.utc).date()
        existing = await self.get_task_slot(user_id, group_id, slot)
        if existing:
            existing.task_name = task_name
            existing.is_done = False
            existing.points_awarded = 0
            existing.completed_at = None
            await self.session.flush()
            return existing
        task = UserDailyTask(
            user_id=user_id,
            group_id=group_id,
            date=today,
            slot=slot,
            task_name=task_name,
        )
        self.session.add(task)
        await self.session.flush()
        return task

    async def mark_task_done(
        self, user_id: int, group_id: int, slot: int, points: int
    ) -> UserDailyTask | None:
        """Mark a task slot as done and record points. Returns the updated task."""
        task = await self.get_task_slot(user_id, group_id, slot)
        if not task or task.is_done:
            return task
        task.is_done = True
        task.points_awarded = points
        task.completed_at = datetime.now(timezone.utc)
        await self.session.flush()
        return task

    async def count_done_today(self, user_id: int, group_id: int) -> int:
        today = datetime.now(timezone.utc).date()
        result = await self.session.execute(
            select(UserDailyTask)
            .where(
                UserDailyTask.user_id == user_id,
                UserDailyTask.group_id == group_id,
                UserDailyTask.date == today,
                UserDailyTask.is_done == True,
            )
        )
        return len(result.scalars().all())

    async def get_today_points(self, user_id: int, group_id: int) -> int:
        """Sum of points_awarded for all done tasks today."""
        tasks = await self.get_today_tasks(user_id, group_id)
        return sum(t.points_awarded for t in tasks)


# ─────────────────────────────────────
# NEW: Skip token repo
# ─────────────────────────────────────

class SkipRepo(BaseRepo):
    """Manages the once-per-week skip token."""

    async def get_skip_record(
        self, user_id: int, group_id: int, week_start: date_type
    ) -> SkipRecord | None:
        result = await self.session.execute(
            select(SkipRecord)
            .where(
                SkipRecord.user_id == user_id,
                SkipRecord.group_id == group_id,
                SkipRecord.week_start == week_start,
            )
        )
        return result.scalar_one_or_none()

    async def create_skip(
        self,
        user_id: int,
        group_id: int,
        week_start: date_type,
        skip_date: date_type,
    ) -> SkipRecord:
        record = SkipRecord(
            user_id=user_id,
            group_id=group_id,
            week_start=week_start,
            skip_date=skip_date,
        )
        self.session.add(record)
        await self.session.flush()
        return record
