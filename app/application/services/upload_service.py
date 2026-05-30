import os
import uuid
import aiofiles
from fastapi import HTTPException, UploadFile
from uuid import UUID
from typing import Optional
from app.infrastructure.repositories.image_repository import ImageRepository
from app.models.image import Image
from app.DTO.image import ImageEntityType, ImageUploadResponse


class UploadService:

    def __init__(self, upload_dir: str, repository: ImageRepository):
        self.upload_dir = upload_dir
        self.repository = repository

    async def save_image(
        self, 
        file: UploadFile, 
        seller_id: UUID,
        entity_type: ImageEntityType,
        entity_id: Optional[UUID] = None,
        ordering: int = 0
    ) -> ImageUploadResponse:

        allowed_signatures = (
            b"\xff\xd8\xff",
            b"\x89PNG\r\n\x1a\n",
            b"GIF87a",
            b"GIF89a",
            b"RIFF",
        )

        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=415,
                detail="Неподдерживаемый формат",
            )

        os.makedirs(self.upload_dir, exist_ok=True)

        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(self.upload_dir, unique_filename)

        try:
            async with aiofiles.open(file_path, "wb") as out_file:
                content = await file.read()
                if len(content) > 5 * 1024 * 1024:
                    raise HTTPException(status_code=413, detail="Файл больше 5 МБ")
                if not content.startswith(allowed_signatures) or (
                    content.startswith(b"RIFF") and content[8:12] != b"WEBP"
                ):
                    raise HTTPException(status_code=415, detail="Unsupported image format")
                await out_file.write(content)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при сохранении файла: {str(e)}",
            )

        url = f"/static/uploads/{unique_filename}"
        
        image_data = {
            "url": url,
            "ordering": ordering,
        }
        
        if entity_type == ImageEntityType.PRODUCT:
            image_data["product_id"] = entity_id
        elif entity_type == ImageEntityType.SKU:
            image_data["sku_id"] = entity_id
            
        new_image = Image(**image_data)
        saved_image = await self.repository.create(new_image)

        return ImageUploadResponse(
            id=saved_image.id,
            url=saved_image.url,
            ordering=saved_image.ordering,
            entity_type=entity_type,
            entity_id=entity_id
        )
