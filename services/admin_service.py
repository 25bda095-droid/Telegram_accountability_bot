from config import settings
from repositories.user_repo import UserRepo
from repositories.streak_repo import StreakRepo
from repositories.group_settings_repo import GroupSettingsRepo
from repositories.audit_repo import AuditRepo

def _is_admin(actor_id):
    return actor_id in settings.admin_ids

async def ban_user(session, actor_id, group_id, target_id) -> bool:
    if not _is_admin(actor_id):
        return False
    user_repo = UserRepo(session)
    await user_repo.ban(target_id)
    audit_repo = AuditRepo(session)
    await audit_repo.log(actor_id, "ban_user", group_id, target_id)
    return True

async def unban_user(session, actor_id, group_id, target_id) -> bool:
    if not _is_admin(actor_id):
        return False
    user_repo = UserRepo(session)
    await user_repo.unban(target_id)
    audit_repo = AuditRepo(session)
    await audit_repo.log(actor_id, "unban_user", group_id, target_id)
    return True

async def reset_user_streak(session, actor_id, group_id, target_id):
    if not _is_admin(actor_id):
        return
    streak_repo = StreakRepo(session)
    await streak_repo.reset_streak(target_id, group_id)
    audit_repo = AuditRepo(session)
    await audit_repo.log(actor_id, "reset_user_streak", group_id, target_id)

async def configure_group(session, actor_id, group_id, open_hour=None, close_hour=None, welcome_message=None):
    if not _is_admin(actor_id):
        return
    group_settings_repo = GroupSettingsRepo(session)
    kwargs = {}
    if open_hour is not None:
        kwargs["task_window_open_hour"] = open_hour
    if close_hour is not None:
        kwargs["task_window_close_hour"] = close_hour
    if welcome_message is not None:
        kwargs["welcome_message"] = welcome_message
    await group_settings_repo.upsert(group_id, **kwargs)
    audit_repo = AuditRepo(session)
    await audit_repo.log(actor_id, "configure_group", group_id, detail=str(kwargs))

async def get_audit_log(session, group_id, limit=20):
    audit_repo = AuditRepo(session)
    return await audit_repo.get_recent(group_id, limit=limit)