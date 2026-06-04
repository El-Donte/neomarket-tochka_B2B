from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.database import get_session
from app.DTO.sku import (
    ReserveRequest, 
    ReserveResponse, 
    InventoryOrderRequest, 
    InventoryOrderResponse
)
from app.models.outbox import OutboxEvent
from app.infrastructure.repositories.sku_repository import SKURepository
from app.infrastructure.repositories.outbox_repository import OutboxRepository
from app.api.v1.dependencies.key_dependency import verify_service_key

from app.models.idempotency import IdempotencyKey

router = APIRouter()


@router.post("/reserve", response_model=ReserveResponse)
async def reserve_inventory(
    request: ReserveRequest,
    _: None = Depends(verify_service_key),
    session: AsyncSession = Depends(get_session),
):
    repo = SKURepository(session)
    outbox_repo = OutboxRepository()
    # Check idempotency
    key = str(request.idempotency_key)
    idemp = await session.get(IdempotencyKey, key)
    if idemp and idemp.response_body:
        return ReserveResponse.model_validate_json(idemp.response_body)

    try:
        stocks_to_update = []
        for item in request.items:
            stock = await repo.get_stock(item.sku_id, for_update=True, with_sku=True)
            if not stock or stock.active_quantity < item.quantity:
                raise HTTPException(
                    status_code=409, 
                    detail={"code": "INSUFFICIENT_STOCK", "sku_id": str(item.sku_id)}
                )
            stocks_to_update.append((stock, item))

        out_of_stock_skus = []
        for stock, item in stocks_to_update:
            old_active = stock.active_quantity
            stock.active_quantity -= item.quantity
            stock.reserved_quantity += item.quantity
            stock.updated_at = datetime.now(timezone.utc)
            session.add(stock)

            if old_active > 0 and stock.active_quantity == 0:
                out_of_stock_skus.append((stock.sku_id, stock.sku.product_id))

        for sku_id, product_id in out_of_stock_skus:
            await outbox_repo.add(
                OutboxEvent(
                    destination_service="b2c",
                    event_type="SKU_OUT_OF_STOCK",
                    aggregate_type="sku",
                    aggregate_id=sku_id,
                    idempotency_key=f"sku_oos_{sku_id}_{datetime.now(timezone.utc).timestamp()}",
                    payload={
                        "sku_id": str(sku_id),
                        "product_id": str(product_id),
                        "available_quantity": 0
                    }
                ),
                session=session
            )
            
        response = ReserveResponse(
            order_id=request.order_id,
            status="RESERVED",
            reserved_at=datetime.now(timezone.utc)
        )
        
        session.add(IdempotencyKey(
            key=key,
            response_body=response.model_dump_json(),
            response_status_code=200
        ))
        await session.commit()
        return response
    except Exception as e:
        await session.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/unreserve", response_model=InventoryOrderResponse)
async def unreserve_inventory(
    request: InventoryOrderRequest,
    _: None = Depends(verify_service_key),
    session: AsyncSession = Depends(get_session),
):
    repo = SKURepository(session)
    key = f"unreserve_{request.order_id}"
    idemp = await session.get(IdempotencyKey, key)
    if idemp and idemp.response_body:
        return InventoryOrderResponse.model_validate_json(idemp.response_body)

    try:
        for item in request.items:
            stock = await repo.get_stock(item.sku_id, for_update=True)
            if stock:
                stock.active_quantity += item.quantity
                stock.reserved_quantity -= item.quantity
                stock.updated_at = datetime.now(timezone.utc)
                session.add(stock)
        
        response = InventoryOrderResponse(
            order_id=request.order_id,
            status="UNRESERVED",
            processed_at=datetime.now(timezone.utc)
        )
        session.add(IdempotencyKey(
            key=key,
            response_body=response.model_dump_json(),
            response_status_code=200
        ))
        await session.commit()
        return response
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fulfill", response_model=InventoryOrderResponse)
async def fulfill_inventory(
    request: InventoryOrderRequest,
    _: None = Depends(verify_service_key),
    session: AsyncSession = Depends(get_session),
):
    repo = SKURepository(session)
    key = f"fulfill_{request.order_id}"
    idemp = await session.get(IdempotencyKey, key)
    if idemp and idemp.response_body:
        return InventoryOrderResponse.model_validate_json(idemp.response_body)

    try:
        for item in request.items:
            stock = await repo.get_stock(item.sku_id, for_update=True)
            if stock:
                stock.stock_quantity -= item.quantity
                stock.reserved_quantity -= item.quantity
                stock.updated_at = datetime.now(timezone.utc)
                session.add(stock)
        
        response = InventoryOrderResponse(
            order_id=request.order_id,
            status="FULFILLED",
            processed_at=datetime.now(timezone.utc)
        )
        session.add(IdempotencyKey(
            key=key,
            response_body=response.model_dump_json(),
            response_status_code=200
        ))
        await session.commit()
        return response
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
