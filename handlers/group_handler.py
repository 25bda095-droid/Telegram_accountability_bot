from aiogram import Router
from aiogram.types import ChatMemberUpdated
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, MEMBER, LEFT
from repositories.group_settings_repo import GroupSettingsRepo
from keyboards.task_keyboard import group_main_menu

router = Router()


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=MEMBER))
async def bot_added_to_group(event: ChatMemberUpdated, session):
    group_id = event.chat.id
    group_settings_repo = GroupSettingsRepo(session)
    await group_settings_repo.upsert(group_id, is_active=True)

    await event.bot.send_message(
        group_id,
        "<b>👋 Accountability Bot is here!</b>\n\n"
        "Here's how to stay accountable:\n\n"
        "1️⃣ <b>Submit Your Task</b> — set 1–6 named tasks each day\n"
        "2️⃣ <b>Update Task</b> — mark tasks done to earn points\n"
        "   • Each task: <b>80 ÷ number of tasks</b> points\n"
        "   • Complete ALL tasks: <b>+20 bonus</b>  (max 100 pts/day)\n"
        "3️⃣ <b>Streak bonuses</b>\n"
        "   • 7-day streak  → <b>+100 pts</b>\n"
        "   • 30-day streak → <b>+300 pts</b>  (and every 30 days after)\n"
        "4️⃣ <b>Skip Today</b> — use once per week to protect your streak\n\n"
        "Let's go! 🔥 Use the menu below:",
        parse_mode="HTML",
        reply_markup=group_main_menu(),
    )


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=LEFT))
async def bot_removed_from_group(event: ChatMemberUpdated, session):
    group_settings_repo = GroupSettingsRepo(session)
    await group_settings_repo.set_active(group_id=event.chat.id, active=False)


@router.chat_member()
async def new_member_joined(event: ChatMemberUpdated, session):
    group_settings_repo = GroupSettingsRepo(session)
    settings_record = await group_settings_repo.get(event.chat.id)
    if settings_record and getattr(settings_record, "welcome_message", None):
        await event.bot.send_message(event.chat.id, settings_record.welcome_message)
