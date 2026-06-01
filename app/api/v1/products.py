from fastapi import APIRouter, Depends, Query, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Union, List
from uuid import UUID

from app.database import get_session
from app.api.v1.dependencies.seller_depends import get_current_seller, get_optional_current_seller
from app.core.config import settings
from app.DTO.product import (
    ProductCreate, 
    ProductResponse, 
    ProductUpdate, 
    ProductDashboardItem, 
    ProductPaginatedResponse, 
    ProductPublicResponse
)
from app.DTO.sku import SKURead
from app.infrastructure.repositories.product_repository import ProductRepository
from app.infrastructure.repositories.category_repository import CategoryRepository
from app.infrastructure.repositories.outbox_repository import OutboxRepository
from app.application.services.product_service import ProductService
from app.DTO.image import ImageResponse, ImageUpdate, ImageAttachRequest

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_session)) -> ProductService:
    return ProductService(ProductRepository(session), CategoryRepository(session), OutboxRepository())


@router.get("", response_model=ProductPaginatedResponse)
async def list_my_products(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    include_deleted: bool = Query(False),
    seller_id: UUID = Depends(get_current_seller),
    service: ProductService = Depends(get_service),
):
    return await service.list_my_products(seller_id, limit, offset, status, include_deleted)


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(
    product_in: ProductCreate,
    seller_id: UUID = Depends(get_current_seller),
    service: ProductService = Depends(get_service),
):
    return await service.create_product(product_in, seller_id)


@router.get("/{product_id}", response_model=Union[ProductResponse, ProductPublicResponse])
async def get_product(
    product_id: UUID,
    x_service_key: Optional[str] = Header(None, alias="X-Service-Key"),
    seller_id: Optional[UUID] = Depends(get_optional_current_seller),
    service: ProductService = Depends(get_service),
):
    product = await service.get_product(product_id)
    if x_service_key:
        if x_service_key != settings.B2B_SERVICE_KEY:
            raise HTTPException(status_code=401, detail="Invalid service key")
        return ProductPublicResponse.model_validate(product)
    
    if seller_id is None:
        raise HTTPException(status_code=401, detail="Authorization required")
    
    if product.seller_id != seller_id:
        raise HTTPException(status_code=404, detail="Access denied")
    return product


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: UUID,
    product_in: ProductUpdate,
    seller_id: UUID = Depends(get_current_seller),
    service: ProductService = Depends(get_service),
):
    return await service.update_product(product_id, product_in, seller_id)


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: UUID,
    seller_id: UUID = Depends(get_current_seller),
    service: ProductService = Depends(get_service),
):
    await service.delete_product(product_id, seller_id)


@router.get("/{product_id}/skus", response_model=List[SKURead])
async def list_product_skus(
    product_id: UUID,
    seller_id: Optional[UUID] = Depends(get_optional_current_seller),
    service: ProductService = Depends(get_service),
    x_service_key: Optional[str] = Header(None, alias="X-Service-Key")
):
    if x_service_key:
        if x_service_key != settings.B2B_SERVICE_KEY:
            raise HTTPException(status_code=401, detail="Invalid service key")
        skus = await service.repo.get_skus_by_product(product_id)
        return [SKURead.model_validate(sku) for sku in skus]

    if seller_id is None:
        raise HTTPException(status_code=401, detail="Authorization required")
    return await service.get_skus_by_product(product_id, seller_id)


@router.post("/{product_id}/images", response_model=ImageResponse, status_code=201)
async def add_product_image(
    product_id: UUID,
    image_in: ImageAttachRequest,
    seller_id: UUID = Depends(get_current_seller),
    service: ProductService = Depends(get_service),
):
    return await service.add_product_image(product_id, image_in, seller_id)


@router.patch("/images/{image_id}", response_model=ImageResponse)
async def update_product_image(
    image_id: UUID,
    image_in: ImageUpdate,
    seller_id: UUID = Depends(get_current_seller),
    service: ProductService = Depends(get_service),
):
    return await service.update_product_image(image_id, image_in, seller_id)


@router.delete("/images/{image_id}", status_code=204)
async def delete_product_image(
    image_id: UUID,
    seller_id: UUID = Depends(get_current_seller),
    service: ProductService = Depends(get_service),
):
    await service.delete_product_image(image_id, seller_id)

@router.get("/dashboard/", response_model=list[ProductDashboardItem], include_in_schema=False)
async def get_products_dashboard(
    seller_id: UUID = Depends(get_current_seller),
    service: ProductService = Depends(get_service),
    status: Optional[str] = Query(None),
):
    return await service.get_dashboard(seller_id, status)


@router.post("/{id}/submit", response_model=ProductResponse, include_in_schema=False)
async def submit_product_for_moderation(
    id: UUID,
    seller_id: UUID = Depends(get_current_seller),
    service: ProductService = Depends(get_service),
):
    return await service.submit_for_moderation(id, seller_id)
