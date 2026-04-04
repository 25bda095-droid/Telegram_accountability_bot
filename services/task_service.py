from dataclasses import dataclass, field
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from config import settings
from repositories.user_repo import UserRepo
from repositories.task_repo import TaskRepo
from repositories.streak_repo import StreakRepo
from repositories.group_settings_repo import GroupSettingsRepo
from services.point_engine import calculate_points
from services.streak_engine import calculate_new_streak
from services.achievement_service import check_and_award

@dataclass
class SubmitResult:
    success: bool
    error_code: Optional[str] = None   # "window_closed" | "already_submitted" | "banned" | "rate_limited" | "no_proof"
    points_awarded: int = 0
    new_streak: int = 0
    achievements_unlocked: List[str] = field(default_factory=list)

async def submit_task(
    session: AsyncSession,
    user_id: int,
    group_id: int,
    proof_text: Optional[str],
    proof_file_id: Optional[str],
) -> SubmitResult:
    # 1. Load group settings → determine effective open/close hours
    group_settings_repo = GroupSettingsRepo(session)
    group_settings = await group_settings_repo.get(group_id)
    open_hour = getattr(group_settings, "task_window_open_hour", None) or settings.task_window_open_hour
    close_hour = getattr(group_settings, "task_window_close_hour", None) or settings.task_window_close_hour

    # 2. Check if current UTC hour is within window → if not, return error_code="window_closed"
    from datetime import datetime, timezone
    now_utc = datetime.now(timezone.utc)
    if not (open_hour <= now_utc.hour < close_hour):
        return SubmitResult(success=False, error_code="window_closed")

    # 3. Fetch user from user_repo → if is_banned, return error_code="banned"
    user_repo = UserRepo(session)
    user = await user_repo.get_by_id(user_id)
    if not user or getattr(user, "is_banned", False):
        return SubmitResult(success=False, error_code="banned")

    # 4. Check today's submission via task_repo.get_today_submission() → if exists, return error_code="already_submitted"
    task_repo = TaskRepo(session)
    existing = await task_repo.get_today_submission(user_id, group_id)
    if existing:
        return SubmitResult(success=False, error_code="already_submitted")

    # 5. Validate proof: at least one of proof_text or proof_file_id must be non-None → if both None, return error_code="no_proof"
    if not (proof_text or proof_file_id):
        return SubmitResult(success=False, error_code="no_proof")

    # 6. Get current streak via streak_repo.get_streak() → call streak_engine.calculate_new_streak()
    streak_repo = StreakRepo(session)
    streak = await streak_repo.get_streak(user_id, group_id)
    last_date = getattr(streak, "last_submission_date", None) if streak else None
    current_streak = getattr(streak, "current_streak", 0) if streak else 0
    new_streak = calculate_new_streak(last_date, current_streak)

    # 7. Calculate points via point_engine.calculate_points(settings.base_points, new_streak)
    points = calculate_points(settings.base_points, new_streak)

    # 8. Write TaskSubmission via task_repo.create_submission()
    await task_repo.create_submission(
        user_id, group_id, proof_text, proof_file_id, points, new_streak
    )

    # 9. Upsert streak via streak_repo.upsert_streak()
    await streak_repo.upsert_streak(user_id, group_id, new_streak, now_utc.date())

    # 10. Add points via user_repo.update_points()
    await user_repo.update_points(user_id, points)

    # 11. Check and award achievements via achievement_service.check_and_award()
    unlocked = await check_and_award(
        session, user_id, group_id, new_streak, user.total_points + points, is_first_submission=(current_streak == 0)
    )

    # 12. Return SubmitResult(success=True, points_awarded=points, new_streak=new_streak, achievements_unlocked=[...])
    return SubmitResult(
        success=True,
        points_awarded=points,
        new_streak=new_streak,
        achievements_unlocked=unlocked
    )