from aiogram.enums import ParseMode

USER_ERRORS = {
    "window_closed": "⏰ Submissions are closed right now.",
    "already_submitted": "✅ You have already submitted for today.",
    "banned": "🚫 You are banned from submitting.",
    "rate_limited": "⏳ Please wait before submitting again.",
    "no_proof": "❗ Please provide proof (text or file).",
    "unknown": "⚠️ An unknown error occurred. Please try again later.",
}

async def send_submission_success(bot, chat_id, user_id, points, streak, achievements):
    msg = (
        f"🎉 <b>Submission received!</b>\n"
        f"<i>Points:</i> <b>{points}</b>\n"
        f"<i>Streak:</i> <b>{streak}</b>"
    )
    if achievements:
        msg += "\n🏅 <b>Achievements unlocked:</b> " + ", ".join(f"<b>{a}</b>" for a in achievements)
    await bot.send_message(chat_id, msg, parse_mode=ParseMode.HTML)

async def send_leaderboard(bot, chat_id, entries):
    lines = ["🏆 <b>Leaderboard</b>"]
    for entry in entries:
        lines.append(
            f"{entry['rank']}. <b>{entry['full_name']}</b> — <i>{entry['points']} pts</i> | 🔥 <i>{entry['streak']}</i>"
        )
    await bot.send_message(chat_id, "\n".join(lines), parse_mode=ParseMode.HTML)

async def send_window_open(bot, chat_id):
    await bot.send_message(chat_id, "🟢 <b>Submission window is now OPEN!</b>", parse_mode=ParseMode.HTML)

async def send_window_close(bot, chat_id, snapshot):
    lines = ["🔴 <b>Submission window is now CLOSED!</b>", "🏆 <b>Today's Top:</b>"]
    for entry in snapshot:
        lines.append(
            f"{entry['rank']}. <b>{entry['full_name']}</b> — <i>{entry['points']} pts</i> | 🔥 <i>{entry['streak']}</i>"
        )
    await bot.send_message(chat_id, "\n".join(lines), parse_mode=ParseMode.HTML)

async def send_achievement_unlocked(bot, chat_id, user_id, achievement_key):
    await bot.send_message(
        chat_id,
        f"🏅 <b>Achievement unlocked:</b> <b>{achievement_key}</b>",
        parse_mode=ParseMode.HTML
    )

async def send_daily_summary(bot, chat_id, stats):
    msg = (
        f"📊 <b>Daily Summary</b>\n"
        f"Total submissions: <b>{stats.get('total_submissions', 0)}</b>\n"
        f"Top user: <b>{stats.get('top_user', 'N/A')}</b>\n"
        f"Total points awarded: <b>{stats.get('total_points', 0)}</b>"
    )
    await bot.send_message(chat_id, msg, parse_mode=ParseMode.HTML)

async def send_error(bot, chat_id, error_code):
    msg = USER_ERRORS.get(error_code, USER_ERRORS["unknown"])
    await bot.send_message(chat_id, msg, parse_mode=ParseMode.HTML)