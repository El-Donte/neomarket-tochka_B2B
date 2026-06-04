# app/infrastructure/repositories/blocking_reason_repository.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from app.models.blocking_reason import BlockingReason

class BlockingReasonRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_from_dto(self, reason_data: dict) -> None:
        """Создать или обновить запись по данным из сервиса модерации."""
        stmt = select(BlockingReason).where(BlockingReason.id == reason_data["id"])
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.code = reason_data.get("code")
            existing.title = reason_data.get("title")
            existing.description = reason_data.get("description")
            existing.hard_block = reason_data.get("hard_block", False)
            existing.is_active = reason_data.get("is_active", True)
        else:
            new_reason = BlockingReason(
                id=reason_data["id"],
                code=reason_data["code"],
                title=reason_data["title"],
                description=reason_data.get("description"),
                hard_block=reason_data.get("hard_block", False),
                is_active=reason_data.get("is_active", True),
            )
            self.session.add(new_reason)

    async def deactivate_missing_ids(self, active_ids: list[UUID]) -> None:
        """Пометить is_active=False для тех id, которых нет в пришедшем списке."""
        stmt = select(BlockingReason).where(BlockingReason.id.not_in(active_ids))
        result = await self.session.execute(stmt)
        missing = result.scalars().all()
        for reason in missing:
            reason.is_active = False