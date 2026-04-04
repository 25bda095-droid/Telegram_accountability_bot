from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, user):
    if message.chat.type == "private":
        await message.answer(
            f"<b>Welcome, {user.full_name}!</b>\n\n"
            "I'm the Accountability Bot. Add me to a group to get started.\n\n"
            "Commands:\n"
            "/submit — Submit your daily task\n"
            "/leaderboard — View group standings\n"
            "/mystats — Your personal stats\n"
            "/achievements — Your badges",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"<b>Accountability Bot is active!</b>\n"
            "Use /submit to complete your daily task. Good luck! 💪",
            parse_mode="HTML"
        )

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "<b>Available Commands</b>\n\n"
        "/submit — Submit today's task completion\n"
        "/leaderboard — View the group leaderboard\n"
        "/mystats — Your points, streak, and rank\n"
        "/achievements — Your earned badges\n"
        "/help — Show this message",
        parse_mode="HTML"
    )