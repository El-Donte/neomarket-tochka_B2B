from fastapi import APIRouter, UploadFile, File, Depends, Form
from uuid import UUID
from typing import Optional

from app.api.v1.dependencies.seller_depends import get_current_seller
from app.application.services.upload_service import UploadService
from app.infrastructure.repositories.image_repository import ImageRepository
from app.database import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from app.DTO.image import ImageEntityType, ImageUploadResponse

UPLOAD_DIR = "app/static/uploads"

router = APIRouter()


def get_service(session: AsyncSession = Depends(get_session)) -> UploadService:
    return UploadService(upload_dir=UPLOAD_DIR, repository=ImageRepository(session))


@router.post("", response_model=ImageUploadResponse, status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    entity_type: ImageEntityType = Form(...),
    entity_id: Optional[UUID] = Form(None),
    ordering: int = Form(0),
    seller_id: UUID = Depends(get_current_seller),
    service: UploadService = Depends(get_service),
):
    return await service.save_image(
        file=file, 
        seller_id=seller_id,
        entity_type=entity_type,
        entity_id=entity_id,
        ordering=ordering
    )
