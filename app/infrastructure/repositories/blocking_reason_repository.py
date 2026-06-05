# app/infrastructure/repositories/blocking_reason_repository.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from app.models.blocking_reason import BlockingReason

class BlockingReasonRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_from_dto(self, reason_data: dict):
        stmt = select(BlockingReason).where(BlockingReason.id == reason_data["id"])
        result = await self.session.exec(stmt)   # вместо execute
        existing = result.first()
        if existing:
            existing.code = reason_data["code"]
            existing.title = reason_data["title"]
            existing.description = reason_data.get("description")
            existing.hard_block = reason_data["hard_block"]
            existing.is_active = reason_data.get("is_active", True)
            self.session.add(existing)
        else:
            new_reason = BlockingReason(**reason_data)
            self.session.add(new_reason)
        # Не делаем commit здесь, он будет в sync_blocking_reasons после всех upsert

    async def deactivate_missing_ids(self, active_ids: list[UUID]):
        stmt = select(BlockingReason).where(BlockingReason.id.not_in(active_ids))
        result = await self.session.exec(stmt)
        missing = result.all()
        for reason in missing:
            reason.is_active = False
            self.session.add(reason)