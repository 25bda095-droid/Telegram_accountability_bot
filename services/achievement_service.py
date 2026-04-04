from repositories.achievement_repo import AchievementRepo

async def check_and_award(
    session,
    user_id: int,
    group_id: int,
    streak: int,
    total_points: int,
    is_first_submission: bool = False,
    snapshot_rank: int | None = None,
    weekly_rank: int | None = None,
) -> list[str]:
    """Check all achievement conditions. Award newly earned ones. Return list of newly unlocked keys."""
    unlocked = []
    candidates = []

    if is_first_submission:
        candidates.append("first_submission")
    if streak >= 3:
        candidates.append("streak_3")
    if streak >= 7:
        candidates.append("streak_7")
    if streak >= 14:
        candidates.append("streak_14")
    if streak >= 30:
        candidates.append("streak_30")
    if total_points >= 100:
        candidates.append("century_points")
    if snapshot_rank == 1:
        candidates.append("top1_daily")
    if weekly_rank is not None and 1 <= weekly_rank <= 3:
        candidates.append("top3_weekly")

    achievement_repo = AchievementRepo(session)
    for key in candidates:
        result = await achievement_repo.award(user_id, group_id, key)
        if result is not None:
            unlocked.append(key)

    return unlocked