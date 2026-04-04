from sqlalchemy import select
from models.db_models import AuditLog
from .base_repo import BaseRepo

class AuditRepo(BaseRepo):
    async def log(self, actor_id: int, action: str, group_id: int, target_id: int | None = None, detail: str | None = None):
        log_entry = AuditLog(
            actor_id=actor_id,
            action=action,
            group_id=group_id,
            target_id=target_id,
            detail=detail
        )
        self.session.add(log_entry)
        await self.session.flush()

    async def get_recent(self, group_id: int, limit: int = 50) -> list[AuditLog]:
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.group_id == group_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()