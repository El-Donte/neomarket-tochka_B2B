from sqlmodel import select, update, case
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime, timezone, timedelta
from typing import List, Callable, Awaitable, Optional


from app.models.outbox import OutboxEvent, OutboxStatus


class OutboxRepository:
    def __init__(self, session_factory: Optional[Callable[[], AsyncSession]] = None):
        self.session_factory = session_factory

    async def add(self, event: OutboxEvent, session: AsyncSession):
        session.add(event)

    async def fetch_pending_events(self, limit: int = 10) -> List[OutboxEvent]:
        if self.session_factory is None:
            raise RuntimeError("OutboxRepository requires session_factory for worker operations")
        async with self.session_factory() as session:
            # Используем FOR UPDATE SKIP LOCKED для параллельной работы нескольких воркеров
            stmt = (
                select(OutboxEvent)
                .where(OutboxEvent.status == OutboxStatus.PENDING)
                .where(
                    (OutboxEvent.locked_at == None) | 
                    (OutboxEvent.locked_at < datetime.now(timezone.utc) - timedelta(minutes=5))
                )
                .order_by(OutboxEvent.created_at.asc())
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
            result = await session.execute(stmt)
            events = result.scalars().all()
            
            if events:
                for event in events:
                    event.status = OutboxStatus.PROCESSING
                    event.locked_at = datetime.now(timezone.utc)
                await session.commit()
                # Возвращаем объекты, отвязанные от сессии (expunge), 
                # либо работаем в рамках сессии, если нужно. 
                # Для упрощения здесь просто возвращаем.
            return events

    async def mark_as_sent(self, event_id: UUID):
        if self.session_factory is None:
            raise RuntimeError("OutboxRepository requires session_factory for worker operations")
        async with self.session_factory() as session:
            await session.execute(
                update(OutboxEvent)
                .where(OutboxEvent.id == event_id)
                .values(status=OutboxStatus.SENT, processed_at=datetime.now(timezone.utc), locked_at=None)
            )
            await session.commit()

    async def increment_retry(self, event_id: UUID, max_retries: int = 3):
        if self.session_factory is None:
            raise RuntimeError("OutboxRepository requires session_factory for worker operations")
        async with self.session_factory() as session:
            # Атомарное обновление
            stmt = (
                update(OutboxEvent)
                .where(OutboxEvent.id == event_id)
                .values(
                    retry_count=OutboxEvent.retry_count + 1,
                    status=select(
                        case(
                            (OutboxEvent.retry_count + 1 >= max_retries, OutboxStatus.FAILED),
                            else_=OutboxStatus.PENDING
                        )
                    ).where(OutboxEvent.id == event_id).scalar_subquery(),
                    locked_at=None
                )
            )
            await session.execute(stmt)
            await session.commit()