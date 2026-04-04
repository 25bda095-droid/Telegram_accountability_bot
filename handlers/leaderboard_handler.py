from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from services import leaderboard_service, notification_service
from repositories.streak_repo import StreakRepo
from repositories.achievement_repo import AchievementRepo

router = Router()

@router.message(Command("leaderboard", "lb"))
async def cmd_leaderboard(message: Message, session):
    group_id = message.chat.id
    entries = await leaderboard_service.get_leaderboard(session, group_id)
    await notification_service.send_leaderboard(message.bot, message.chat.id, entries)

@router.message(Command("mystats"))
async def cmd_mystats(message: Message, user, session):
    streak_repo = StreakRepo(session)
    achievement_repo = AchievementRepo(session)
    group_id = message.chat.id

    # Query stats
    current_streak = 0
    longest_streak = 0
    streak = await streak_repo.get_streak(user.id, group_id)
    if streak:
        current_streak = getattr(streak, "current_streak", 0)
        longest_streak = getattr(streak, "longest_streak", 0)
    achievements = await achievement_repo.get_user_achievements(user.id, group_id)
    achievement_count = len(achievements)
    total_points = getattr(user, "total_points", 0)

    # Format and send personal stats card
    msg = (
        f"<b>Your Stats</b>\n\n"
        f"Points: <b>{total_points}</b>\n"
        f"Current streak: <b>{current_streak}</b>\n"
        f"Longest streak: <b>{longest_streak}</b>\n"
        f"Achievements: <b>{achievement_count}</b>"
    )
    await message.answer(msg, parse_mode="HTML")