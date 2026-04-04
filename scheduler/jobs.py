import logging
from datetime import date, timedelta
from repositories.group_settings_repo import GroupSettingsRepo
from repositories.snapshot_repo import SnapshotRepo
from repositories.streak_repo import StreakRepo
from repositories.user_repo import UserRepo
from services import notification_service, leaderboard_service, achievement_service, point_engine


async def job_open_task_window(bot, session_factory):
    """Daily at task_window_open_hour UTC. Post window-open message to all active groups."""
    logging.info("Scheduler: opening task window")
    async with session_factory() as session:
        group_settings_repo = GroupSettingsRepo(session)
        active_groups = await group_settings_repo.get_all_active()
    for group in active_groups:
        try:
            await notification_service.send_window_open(bot, group.group_id)
        except Exception as e:
            logging.warning(f"Could not notify group {group.group_id}: {e}")


async def job_close_task_window(bot, session_factory):
    """Daily at task_window_close_hour UTC. Take snapshot + post daily summary."""
    logging.info("Scheduler: closing task window")
    async with session_factory() as session:
        group_settings_repo = GroupSettingsRepo(session)
        snapshot_repo = SnapshotRepo(session)
        active_groups = await group_settings_repo.get_all_active()
        for group in active_groups:
            try:
                await leaderboard_service.take_daily_snapshot(session, group.group_id)
                snapshot = await snapshot_repo.get_snapshot(group.group_id, date.today())
                await notification_service.send_window_close(bot, group.group_id, snapshot)
                await session.commit()
            except Exception as e:
                logging.error(f"Error closing window for group {group.group_id}: {e}", exc_info=True)


async def job_check_broken_streaks(bot, session_factory):
    """Daily at 00:05 UTC. Reset streaks for users who missed yesterday."""
    logging.info("Scheduler: checking broken streaks")
    yesterday = date.today() - timedelta(days=1)
    async with session_factory() as session:
        streak_repo = StreakRepo(session)
        broken_streaks = await streak_repo.get_broken_streaks(yesterday)
        for streak in broken_streaks:
            await streak_repo.reset_streak(streak.user_id, streak.group_id)
        await session.commit()


async def job_weekly_summary(bot, session_factory):
    """Every Monday 00:05 UTC. Compute top 3, award top3_weekly, post recap."""
    logging.info("Scheduler: weekly summary")
    async with session_factory() as session:
        group_settings_repo = GroupSettingsRepo(session)
        user_repo = UserRepo(session)
        active_groups = await group_settings_repo.get_all_active()
        for group in active_groups:
            try:
                entries = await leaderboard_service.get_leaderboard(session, group.group_id, limit=3)
                for i, entry in enumerate(entries[:3], start=1):
                    await achievement_service.check_and_award(
                        session, entry["user_id"], group.group_id,
                        streak=entry["streak"], total_points=entry["points"],
                        snapshot_rank=i,
                        weekly_rank=i
                    )
                    points_bonus = point_engine.weekly_bonus(i)
                    await user_repo.update_points(entry["user_id"], points_bonus)
                await notification_service.send_daily_summary(bot, group.group_id, {"top3": entries})
                await session.commit()
            except Exception as e:
                logging.error(f"Weekly summary error for group {group.group_id}: {e}", exc_info=True)


async def job_daily_leaderboard(bot, session_factory):
    """Daily at 21:00 UTC. Post leaderboard + top streak to all active groups."""
    logging.info("Scheduler: daily leaderboard")
    async with session_factory() as session:
        group_settings_repo = GroupSettingsRepo(session)
        active_groups = await group_settings_repo.get_all_active()
        for group in active_groups:
            try:
                entries = await leaderboard_service.get_leaderboard(session, group.group_id, limit=10)
                if not entries:
                    continue

                medals = ["🥇", "🥈", "🥉"]
                lines = ["🏆 <b>Daily Leaderboard</b>\n"]

                top_streak_entry = None
                top_streak = 0

                for e in entries:
                    prefix = medals[e["rank"] - 1] if e["rank"] <= 3 else f"{e['rank']}."
                    name   = f"@{e['username']}" if e.get("username") else e["full_name"]
                    lines.append(f"{prefix} <b>{name}</b> — {e['points']} pts  🔥{e['streak']}")
                    if e["streak"] > top_streak:
                        top_streak = e["streak"]
                        top_streak_entry = e

                if top_streak_entry and top_streak > 0:
                    top_name = (
                        f"@{top_streak_entry['username']}"
                        if top_streak_entry.get("username")
                        else top_streak_entry["full_name"]
                    )
                    lines.append(f"\n👑 <b>Highest Streak:</b> <b>{top_name}</b> — {top_streak} days 🔥")

                await bot.send_message(group.group_id, "\n".join(lines), parse_mode="HTML")
                await session.commit()
            except Exception as e:
                logging.error(f"Daily leaderboard error for group {group.group_id}: {e}", exc_info=True)
