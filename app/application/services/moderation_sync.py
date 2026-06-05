import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.repositories.blocking_reason_repository import BlockingReasonRepository
from app.core.config import settings

async def sync_blocking_reasons(session: AsyncSession) -> None:
    """Загрузить все причины блокировки из сервиса модерации и обновить локальную таблицу."""
    url = f"{settings.MODERATION_SERVICE_URL}/api/v1/blocking-reasons/list"
    headers = {"X-Service-Key": settings.MODERATION_SERVICE_KEY}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        reasons = response.json()

    repo = BlockingReasonRepository(session)

    active_ids = []
    for item in reasons:
        reason_data = {
            "id": item["id"],
            "code": item["code"],
            "title": item["title"],
            "description": item.get("description"),
            "hard_block": item.get("hard_block", False),
            "is_active": item.get("is_active", True),
        }
        await repo.upsert_from_dto(reason_data)
        active_ids.append(reason_data["id"])

    await repo.deactivate_missing_ids(active_ids)
    await session.commit()