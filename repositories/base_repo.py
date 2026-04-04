from sqlalchemy.ext.asyncio import AsyncSession

class BaseRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def commit(self):
        await self.session.commit()

    async def flush(self):
        await self.session.flush()