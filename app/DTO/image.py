from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field
from enum import Enum

class ImageEntityType(str, Enum):
    PRODUCT = "PRODUCT"
    SKU = "SKU"

class ImageCreate(BaseModel):
    url: str
    ordering: int = Field(default=0, ge=0)

class ImageAttachRequest(BaseModel):
    image_id: Optional[UUID] = None
    url: Optional[str] = None
    ordering: int = Field(default=0, ge=0)

class ImageUploadResponse(BaseModel):
    id: UUID
    url: str
    ordering: int
    entity_type: ImageEntityType
    entity_id: Optional[UUID] = None

class ImageResponse(BaseModel):
    id: UUID
    url: str
    ordering: int

    model_config = {"from_attributes": True}

class ImageUpdate(BaseModel):
    url: Optional[str] = None
    ordering: Optional[int] = Field(default=0, ge=0)
