from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.DTO.seller import SellerResponse, SellerUpdate
from app.application.services.seller_service import SellerService
from app.infrastructure.repositories.seller_repository import SellerRepository
from app.api.v1.dependencies.seller_depends import get_current_seller
from app.database import get_session

router = APIRouter()


async def get_seller_service(db: AsyncSession = Depends(get_session)):
    return SellerService(SellerRepository(db))

@router.get(
    "/me",
    response_model=SellerResponse,
    summary="Мой профиль",
)
async def get_my_profile(
    seller_id: UUID = Depends(get_current_seller),
    service: SellerService = Depends(get_seller_service)
):
    return await service.get_my_profile(seller_id)


@router.patch(
    "/me",
    response_model=SellerResponse,
    summary="Обновить профиль",
)
async def update_profile(
    data: SellerUpdate,
    seller_id: UUID = Depends(get_current_seller),
    service: SellerService = Depends(get_seller_service)
):
    return await service.update_profile(seller_id, data)


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить аккаунт",
)
async def delete_profile(
    seller_id: UUID = Depends(get_current_seller),
    service: SellerService = Depends(get_seller_service)
):
    await service.delete_profile(seller_id)