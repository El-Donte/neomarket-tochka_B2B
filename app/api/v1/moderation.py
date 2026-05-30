from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime, timezone
from typing import List

from app.database import get_session
from app.DTO.product import ModerationEventRequest, ProductStatus
from app.infrastructure.repositories.product_repository import ProductRepository

from app.models.idempotency import IdempotencyKey
from app.models.outbox import OutboxEvent
from app.api.v1.dependencies.key_dependency import verify_service_key

router = APIRouter()


@router.post("/events", status_code=204)
async def receive_moderation_event(
    request: ModerationEventRequest,
    _: None = Depends(verify_service_key),
    session: AsyncSession = Depends(get_session),
):
    key = f"moderation_{request.idempotency_key}"
    idemp = await session.get(IdempotencyKey, key)
    if idemp:
        return

    repo = ProductRepository(session)
    product = await repo.get_by_id(request.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    if request.event_type == "MODERATED":
        product.status = ProductStatus.MODERATED
    elif request.event_type == "BLOCKED":
        if request.blocking_reason_id is None:
            raise HTTPException(
                status_code=400,
                detail={"code": "BAD_REQUEST", "message": "blocking_reason_id is required for BLOCKED"},
            )
        if request.hard_block:
            product.status = ProductStatus.HARD_BLOCKED
        else:
            product.status = ProductStatus.BLOCKED
        
        product.blocking_reason_id = request.blocking_reason_id
        product.moderator_comment = request.moderator_comment
        if any(sku.active_quantity > 0 for sku in product.skus):
            session.add(
                OutboxEvent(
                    destination_service="b2c",
                    event_type="PRODUCT_BLOCKED",
                    aggregate_type="PRODUCT",
                    aggregate_id=product.id,
                    idempotency_key=f"b2c:PRODUCT_BLOCKED:{product.id}:{request.idempotency_key}",
                    payload={"product_id": str(product.id), "hard_block": request.hard_block},
                )
            )

    product.updated_at = datetime.now(timezone.utc)
    
    await repo.save(product)
    
    session.add(IdempotencyKey(
        key=key,
        response_status_code=204
    ))
    await session.commit()
    return
