from fastapi import APIRouter, Depends, Query, status
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from uuid import UUID

from app.database import get_session
from app.DTO.category import (
    CategoryCreate,
    CategoryUpdate,
    CategoryResponse,
    CategoryWithChildrenResponse,
    CategoryTreeResponse
)
from app.application.services.category_service import CategoryService
from app.infrastructure.repositories.category_repository import CategoryRepository
from app.api.v1.dependencies.seller_depends import require_admin_seller


router = APIRouter()
security = HTTPBearer()


def get_category_service(
    session: AsyncSession = Depends(get_session),
) -> CategoryService:
    return CategoryService(CategoryRepository(session))

@router.get("", response_model=List[CategoryResponse])
async def list_categories(
    parent_id: Optional[UUID] = Query(default=None),
    only_root: bool = Query(default=False),
    service: CategoryService = Depends(get_category_service),
):
    return await service.get_category_list(parent_id, only_root)

@router.post(
    "",
    response_model=CategoryWithChildrenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(security)]
)
async def create_category(
    data: CategoryCreate,
    service: CategoryService = Depends(get_category_service),
    _: UUID = Depends(require_admin_seller)
):
    return await service.create_category(data)

@router.get("/tree", response_model=List[CategoryTreeResponse])
async def get_categories_tree(service: CategoryService = Depends(get_category_service)):
    return await service.get_tree()

@router.get(
    "/{category_id}",
    response_model=CategoryWithChildrenResponse,
)
async def get_category(
    category_id: UUID,
    service: CategoryService = Depends(get_category_service),
):
    return await service.get_category_with_children(category_id)

@router.patch(
    "/{category_id}",
    response_model=CategoryWithChildrenResponse,
    dependencies=[Depends(security)]
)
async def update_category(
    category_id: UUID,
    data: CategoryUpdate,
    service: CategoryService = Depends(get_category_service),
    _: UUID = Depends(require_admin_seller)
):
    return await service.update_category(category_id, data)

@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(security)]
)
async def delete_category(
    category_id: UUID,
    service: CategoryService = Depends(get_category_service),
    _: UUID = Depends(require_admin_seller)
):
    await service.delete_category(category_id)

@router.get("/{category_id}/breadcrumbs", response_model=List[CategoryResponse])
async def get_category_breadcrumbs(
    category_id: UUID,
    service: CategoryService = Depends(get_category_service)
):
    return await service.get_breadcrumbs(category_id)
