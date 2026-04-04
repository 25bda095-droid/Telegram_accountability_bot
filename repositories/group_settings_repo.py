from sqlalchemy import select, update
from models.db_models import GroupSettings
from .base_repo import BaseRepo


class GroupSettingsRepo(BaseRepo):
    async def get(self, group_id: int) -> GroupSettings | None:
        result = await self.session.execute(
            select(GroupSettings).where(GroupSettings.group_id == group_id)
        )
        return result.scalar_one_or_none()

    async def upsert(self, group_id: int, **kwargs) -> GroupSettings:
        settings = await self.get(group_id)
        if settings:
            for key, value in kwargs.items():
                setattr(settings, key, value)
        else:
            settings = GroupSettings(group_id=group_id, **kwargs)
            self.session.add(settings)
        await self.session.flush()
        return settings

    async def set_active(self, group_id: int, active: bool):
        await self.session.execute(
            update(GroupSettings)
            .where(GroupSettings.group_id == group_id)
            .values(is_active=active)
        )

    async def get_all_active(self) -> list[GroupSettings]:
        """Return all groups where is_active = True. Used by all scheduler jobs."""
        result = await self.session.execute(
            select(GroupSettings).where(GroupSettings.is_active == True)
        )
        return result.scalars().all()
