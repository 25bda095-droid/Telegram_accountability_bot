from datetime import date
from cache.ttl_cache import leaderboard_cache
from repositories.user_repo import UserRepo
from repositories.streak_repo import StreakRepo
from repositories.snapshot_repo import SnapshotRepo


async def get_leaderboard(session, group_id: int, limit: int = 10) -> list[dict]:
    cache_key = f"lb:{group_id}"
    cached = leaderboard_cache.get(cache_key)
    if cached is not None:
        return cached

    user_repo = UserRepo(session)
    streak_repo = StreakRepo(session)
    users = await user_repo.get_top_n(group_id, n=limit)
    leaderboard = []
    for idx, user in enumerate(users, start=1):
        streak = 0
        user_streak = await streak_repo.get_streak(user.id, group_id)
        if user_streak:
            streak = user_streak.current_streak
        leaderboard.append({
            "rank": idx,
            "user_id": user.id,
            "username": user.username,        # FIX: added so handler can show @username
            "full_name": user.full_name,
            "points": user.total_points,
            "streak": streak,
        })
    leaderboard_cache.set(cache_key, leaderboard, ttl=300)
    return leaderboard


async def take_daily_snapshot(session, group_id: int):
    user_repo = UserRepo(session)
    streak_repo = StreakRepo(session)
    snapshot_repo = SnapshotRepo(session)
    users = await user_repo.get_top_n(group_id, n=100)
    rankings = []
    for idx, user in enumerate(users, start=1):
        streak = 0
        user_streak = await streak_repo.get_streak(user.id, group_id)
        if user_streak:
            streak = user_streak.current_streak
        rankings.append({
            "rank": idx,
            "user_id": user.id,
            "username": user.username,        # FIX: added for consistency
            "full_name": user.full_name,
            "points": user.total_points,
            "streak": streak,
        })
    await snapshot_repo.save_snapshot(group_id, date.today(), rankings)
    leaderboard_cache.delete(f"lb:{group_id}")
