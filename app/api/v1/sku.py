from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List

from app.database import get_session
from app.api.v1.dependencies.seller_depends import get_current_seller
from app.DTO.sku import SKUCreate, SKUUpdate, SKURead
from app.infrastructure.repositories.sku_repository import SKURepository
from app.infrastructure.repositories.outbox_repository import OutboxRepository
from app.application.services.sku_service import SKUService
from app.DTO.image import ImageResponse, ImageUpdate, ImageAttachRequest


router = APIRouter()


async def get_service(
    session: AsyncSession = Depends(get_session),
) -> SKUService:
    return SKUService(SKURepository(session), OutboxRepository())


@router.post("", response_model=SKURead, status_code=201)
async def create_sku(
    sku_in: SKUCreate,
    seller_id: UUID = Depends(get_current_seller),
    service: SKUService = Depends(get_service),
):
    return await service.create_sku(sku_in, seller_id)


@router.get("/{sku_id}", response_model=SKURead)
async def get_sku(
    sku_id: UUID,
    seller_id: UUID = Depends(get_current_seller),
    service: SKUService = Depends(get_service),
):
    return await service.get_sku(sku_id, seller_id)


@router.patch("/{sku_id}", response_model=SKURead)
async def update_sku(
    sku_id: UUID,
    sku_in: SKUUpdate,
    seller_id: UUID = Depends(get_current_seller),
    service: SKUService = Depends(get_service),
):
    return await service.update_sku(sku_id, sku_in, seller_id)


@router.delete("/{sku_id}", status_code=204)
async def delete_sku(
    sku_id: UUID,
    seller_id: UUID = Depends(get_current_seller),
    service: SKUService = Depends(get_service),
):
    await service.delete_sku(sku_id, seller_id)


@router.post("/{sku_id}/images", response_model=ImageResponse, status_code=201)
async def add_sku_image(
    sku_id: UUID,
    image_in: ImageAttachRequest,
    seller_id: UUID = Depends(get_current_seller),
    service: SKUService = Depends(get_service),
):
    return await service.add_sku_image(sku_id, image_in, seller_id)


@router.patch("/images/{image_id}", response_model=ImageResponse)
async def update_sku_image(
    image_id: UUID,
    image_in: ImageUpdate,
    seller_id: UUID = Depends(get_current_seller),
    service: SKUService = Depends(get_service),
):
    return await service.update_sku_image(image_id, image_in, seller_id)


@router.delete("/images/{image_id}", status_code=204)
async def delete_sku_image(
    image_id: UUID,
    seller_id: UUID = Depends(get_current_seller),
    service: SKUService = Depends(get_service),
):
    await service.delete_sku_image(image_id, seller_id)


# Quest/Internal route kept
@router.get("/inventory/all", response_model=list[dict], include_in_schema=False)
async def get_inventory(
    seller_id: UUID = Depends(get_current_seller),
    service: SKUService = Depends(get_service),
):
    return await service.get_inventory(seller_id)
