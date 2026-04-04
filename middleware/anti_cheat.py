import logging
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from repositories.task_repo import TaskRepo
from repositories.group_settings_repo import GroupSettingsRepo
from config import settings

class AntiCheatMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        message = getattr(event, "message", None)
        if not message:
            return await handler(event, data)

        user = data.get("user")
        session = data.get("session")
        if not user or not session:
            return await handler(event, data)
        user_id = user.id
        group_id = message.chat.id

        # Extract proof_text (text or photo caption)
        proof_text = message.text or (message.caption if hasattr(message, "caption") else None)
        proof_file = None
        if message.photo or message.document:
            proof_file = True

        # No proof check
        if not proof_text and not proof_file:
            await message.answer("❗ Please provide proof (text or file).")
            return

        # Duplicate text check
        task_repo = TaskRepo(session)
        last_submission = await task_repo.get_today_submission(user_id, group_id)
        if last_submission and last_submission.proof_text and proof_text:
            if last_submission.proof_text.strip() == proof_text.strip():
                data["anti_cheat_flag"] = True
                data["anti_cheat_reason"] = "duplicate_text"
                logging.warning(f"Anti-cheat flag: user={user_id} reason=duplicate_text")

        # Suspiciously fast check
        group_settings_repo = GroupSettingsRepo(session)
        group_settings = await group_settings_repo.get(group_id)
        open_hour = getattr(group_settings, "task_window_open_hour", None) or settings.task_window_open_hour

        from datetime import datetime, timezone, time as dtime
        now_utc = datetime.now(timezone.utc)
        window_open = now_utc.replace(hour=open_hour, minute=0, second=0, microsecond=0)
        if (now_utc - window_open).total_seconds() < 5:
            data["anti_cheat_flag"] = True
            data["anti_cheat_reason"] = "suspiciously_fast"
            logging.warning(f"Anti-cheat flag: user={user_id} reason=suspiciously_fast")

        return await handler(event, data)