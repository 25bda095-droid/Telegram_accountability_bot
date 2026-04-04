from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

router = Router()

# 🔹 Main Menu Keyboard
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Submit Task", callback_data="submit")],
        [InlineKeyboardButton(text="🏆 Leaderboard", callback_data="leaderboard")],
        [InlineKeyboardButton(text="📊 My Stats", callback_data="mystats")],
        [InlineKeyboardButton(text="🎯 Achievements", callback_data="achievements")]
    ])


# 🔹 START COMMAND
@router.message(CommandStart())
async def cmd_start(message: Message, user):
    if message.chat.type == "private":
        await message.answer(
            f"<b>🔥 Welcome, {user.full_name}!</b>\n\n"
            "Stay consistent. Build streaks. Win discipline.\n\n"
            "👇 Use buttons below",
            reply_markup=main_menu(),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "<b>🤖 Accountability Bot is active!</b>\n\n"
            "Use the menu below to interact 👇",
            reply_markup=main_menu(),
            parse_mode="HTML"
        )


# 🔹 HELP COMMAND
@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "<b>📌 How to use the bot</b>\n\n"
        "Use the buttons below to interact easily.\n"
        "No need to type commands manually 👇",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )


# 🔹 BUTTON HANDLER (VERY IMPORTANT)
@router.callback_query()
async def handle_buttons(callback: CallbackQuery):

    if callback.data == "submit":
        await callback.message.answer(
            "📸 <b>Submit Your Task</b>\n\n"
            "Send:\n"
            "• Photo OR\n"
            "• Text proof\n\n"
            "Stay consistent 🔥",
            parse_mode="HTML"
        )

    elif callback.data == "leaderboard":
        await callback.message.answer(
            "🏆 <b>Leaderboard</b>\n\nLoading...",
            parse_mode="HTML"
        )

    elif callback.data == "mystats":
        await callback.message.answer(
            "📊 <b>Your Stats</b>\n\nLoading...",
            parse_mode="HTML"
        )

    elif callback.data == "achievements":
        await callback.message.answer(
            "🎯 <b>Your Achievements</b>\n\nLoading...",
            parse_mode="HTML"
        )

    # 🔁 Show menu again after every action
    await callback.message.answer(
        "👇 What next?",
        reply_markup=main_menu()
    )

    await callback.answer()
