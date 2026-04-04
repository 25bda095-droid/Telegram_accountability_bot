from aiogram import Router
from aiogram.types import ChatMemberUpdated
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, MEMBER, LEFT
from repositories.group_settings_repo import GroupSettingsRepo

router = Router()

@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=MEMBER))
async def bot_added_to_group(event: ChatMemberUpdated, session):
    group_id = event.chat.id
    group_settings_repo = GroupSettingsRepo(session)
    await group_settings_repo.upsert(group_id, is_active=True)
    await event.bot.send_message(group_id, "👋 Accountability Bot is ready! Use /submit daily.")

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