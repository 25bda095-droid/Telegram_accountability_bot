from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from repositories.achievement_repo import AchievementRepo

ACHIEVEMENT_DISPLAY = {
    "first_submission": "🌱 First Step",
    "streak_3":         "🔥 3-Day Streak",
    "streak_7":         "⚡ 7-Day Streak",
    "streak_14":        "💎 2-Week Streak",
    "streak_30":        "🏆 30-Day Streak",
    "top1_daily":       "👑 Daily Champion",
    "top3_weekly":      "🥉 Weekly Top 3",
    "century_points":   "💯 Century Club",
}

router = Router()

@router.message(Command("achievements"))
async def cmd_achievements(message: Message, user, session):
    achievement_repo = AchievementRepo(session)
    achievements = await achievement_repo.get_user_achievements(user.id, message.chat.id)
    if not achievements:
        await message.answer("You haven't earned any badges yet. Keep going! 💪")
        return
    lines = []
    for a in achievements:
        label = ACHIEVEMENT_DISPLAY.get(a.achievement_key, a.achievement_key)
        lines.append(f"{label} — <i>{a.awarded_at.strftime('%b %d')}</i>")
    await message.answer("<b>Your Achievements</b>\n\n" + "\n".join(lines), parse_mode="HTML")