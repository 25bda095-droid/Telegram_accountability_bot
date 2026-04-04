from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from keyboards.task_keyboard import group_main_menu, private_main_menu

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, user):
    if message.chat.type == "private":
        await message.answer(
            f"<b>👋 Hey {user.full_name}!</b>\n\n"
            "Here you can check your personal accountability stats.\n\n"
            "➕ <b>Add me to a group</b> to unlock all features:\n"
            "   ✅ Submit & track daily tasks\n"
            "   🔄 Mark tasks done, earn points\n"
            "   🏆 Group leaderboard\n"
            "   🔥 Streaks with weekly & monthly bonuses\n"
            "   ⏭️ Skip token (once per week)\n\n"
            "👇 <b>Your personal stats:</b>",
            reply_markup=private_main_menu(),
            parse_mode="HTML",
        )
    else:
        await message.answer(
            "<b>🤖 Accountability Bot is active!</b>\n\n"
            "Stay consistent. Build streaks. Win discipline. 🔥\n\n"
            "👇 Use the menu below:",
            reply_markup=group_main_menu(),
            parse_mode="HTML",
        )


@router.message(Command("help"))
async def cmd_help(message: Message):
    if message.chat.type == "private":
        await message.answer(
            "<b>📌 How to use</b>\n\n"
            "This bot helps you stay accountable with daily tasks in a group.\n\n"
            "➕ Add me to your group to get started!\n\n"
            "👇 Your personal stats:",
            reply_markup=private_main_menu(),
            parse_mode="HTML",
        )
    else:
        await message.answer(
            "<b>📌 How it works</b>\n\n"
            "1️⃣ <b>Submit Your Task</b> — set 1–6 named tasks for the day\n"
            "2️⃣ <b>Update Task</b> — mark tasks done to earn points\n"
            "   • Each task: 80 ÷ number of tasks = points\n"
            "   • Complete ALL tasks: +20 bonus (max 100/day)\n"
            "3️⃣ <b>Streaks</b> — 7-day streak: +100 pts · 30-day: +300 pts\n"
            "4️⃣ <b>Skip Today</b> — use once per week to protect your streak\n\n"
            "👇 Menu:",
            reply_markup=group_main_menu(),
            parse_mode="HTML",
        )


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    if message.chat.type == "private":
        await message.answer("👇 Your options:", reply_markup=private_main_menu())
    else:
        await message.answer("👇 Main Menu:", reply_markup=group_main_menu())
