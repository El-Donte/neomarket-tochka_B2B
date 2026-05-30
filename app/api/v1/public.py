from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict, Literal
from uuid import UUID
from pydantic import BaseModel, Field

from app.database import get_session
from app.DTO.product import (
    ProductPublicResponse, 
    ProductPublicShortResponse, 
    ProductPublicPaginatedResponse
)
from app.DTO.sku import SKUPublicResponse
from app.infrastructure.repositories.product_repository import ProductRepository
from app.infrastructure.repositories.category_repository import CategoryRepository
from app.infrastructure.repositories.outbox_repository import OutboxRepository
from app.application.services.product_service import ProductService
from app.api.v1.dependencies.key_dependency import verify_service_key

router = APIRouter()


class PublicProductBatchRequest(BaseModel):
    product_ids: List[UUID] = Field(max_length=100)


def get_service(session: AsyncSession = Depends(get_session)):
    repo = ProductRepository(session)
    cat_repo = CategoryRepository(session)
    outbox_repo = OutboxRepository()
    return ProductService(repo, cat_repo, outbox_repo)


@router.get("/products", response_model=ProductPublicPaginatedResponse)
async def list_public_products(
    request: Request,
    _: None = Depends(verify_service_key),
    category_id: Optional[UUID] = Query(None),
    search: Optional[str] = Query(None, min_length=3),
    min_price: Optional[int] = Query(None, ge=0),
    max_price: Optional[int] = Query(None, ge=0),
    seller_id: Optional[UUID] = Query(None),
    sort: Literal["price_asc", "price_desc", "created_desc", "popular"] = Query("created_desc"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: ProductService = Depends(get_service),
):
    filters: dict[str, list[str]] = {}
    for key, value in request.query_params.multi_items():
        if key.startswith("filters[") and key.endswith("]"):
            filter_name = key[len("filters["):-1]
            filters.setdefault(filter_name, []).append(value)

    return await service.get_public_products(
        category_id=category_id,
        search=search,
        min_price=min_price,
        max_price=max_price,
        seller_id=seller_id,
        filters=filters,
        sort=sort,
        limit=limit,
        offset=offset
    )


@router.post("/products/batch", response_model=List[ProductPublicResponse])
async def batch_public_products(
    body: PublicProductBatchRequest,
    _: None = Depends(verify_service_key),
    service: ProductService = Depends(get_service),
):
    return await service.get_public_batch(body.product_ids)


@router.get("/products/{product_id}", response_model=ProductPublicResponse)
async def get_public_product(
    product_id: UUID,
    _: None = Depends(verify_service_key),
    service: ProductService = Depends(get_service),
):
    return await service.get_public_product(product_id)


@router.get("/products/{product_id}/similar", response_model=List[ProductPublicShortResponse])
async def get_public_similar_products(
    product_id: UUID,
    _: None = Depends(verify_service_key),
    limit: int = Query(10, ge=1, le=50),
    service: ProductService = Depends(get_service),
):
    return await service.get_similar_products(product_id, limit)


@router.get("/skus/{sku_id}", response_model=SKUPublicResponse)
async def get_public_sku(
    sku_id: UUID,
    _: None = Depends(verify_service_key),
    service: ProductService = Depends(get_service),
):
    return await service.get_public_sku(sku_id)
