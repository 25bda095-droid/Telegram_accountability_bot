from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from config import settings
from services import admin_service
from keyboards.task_keyboard import admin_keyboard

router = Router()

def is_admin(user):
    return user.id in settings.admin_ids

@router.message(Command("ban"))
async def cmd_ban(message: Message, user, session):
    if not is_admin(user):
        await message.answer("This command is restricted to admins.")
        return
    args = message.get_args().strip()
    if args.startswith("@"):
        # Lookup user_id by username (not implemented here)
        await message.answer("Username lookup not implemented.")
        return
    try:
        target_id = int(args)
    except Exception:
        await message.answer("Usage: /ban <user_id>")
        return
    ok = await admin_service.ban_user(session, user.id, message.chat.id, target_id)
    if ok:
        await message.answer("User banned.")
    else:
        await message.answer("Failed to ban user.")

@router.message(Command("unban"))
async def cmd_unban(message: Message, user, session):
    if not is_admin(user):
        await message.answer("This command is restricted to admins.")
        return
    args = message.get_args().strip()
    if args.startswith("@"):
        await message.answer("Username lookup not implemented.")
        return
    try:
        target_id = int(args)
    except Exception:
        await message.answer("Usage: /unban <user_id>")
        return
    ok = await admin_service.unban_user(session, user.id, message.chat.id, target_id)
    if ok:
        await message.answer("User unbanned.")
    else:
        await message.answer("Failed to unban user.")

@router.message(Command("resetstreak"))
async def cmd_resetstreak(message: Message, user, session):
    if not is_admin(user):
        await message.answer("This command is restricted to admins.")
        return
    args = message.get_args().strip()
    if args.startswith("@"):
        await message.answer("Username lookup not implemented.")
        return
    try:
        target_id = int(args)
    except Exception:
        await message.answer("Usage: /resetstreak <user_id>")
        return
    await admin_service.reset_user_streak(session, user.id, message.chat.id, target_id)
    await message.answer("User streak reset.")

@router.message(Command("config"))
async def cmd_config(message: Message, user, session):
    if not is_admin(user):
        await message.answer("This command is restricted to admins.")
        return
    args = message.get_args()
    kwargs = {}
    for part in args.split():
        if "=" in part:
            k, v = part.split("=", 1)
            if k == "open":
                kwargs["open_hour"] = int(v)
            elif k == "close":
                kwargs["close_hour"] = int(v)
            elif k == "welcome":
                kwargs["welcome_message"] = v
    await admin_service.configure_group(session, user.id, message.chat.id, **kwargs)
    await message.answer("Group configuration updated.")

@router.message(Command("admin"))
async def cmd_admin(message: Message, user):
    if not is_admin(user):
        await message.answer("This command is restricted to admins.")
        return
    await message.answer("Admin panel:", reply_markup=admin_keyboard(message.chat.id))