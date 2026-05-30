from datetime import datetime
from typing import Literal, Optional, List
from app.DTO.sku import SKURead, SKUPublicResponse, CharacteristicCreate, CharacteristicRead
from pydantic import BaseModel, Field
from uuid import UUID

from app.DTO.image import ImageCreate, ImageResponse
from app.models.product import ProductStatus

class ProductCreate(BaseModel):
    """
    Данные для создания товара.
    
    seller_id НЕ передаётся — берётся из токена авторизации.
    """
    title: str = Field(min_length=1, max_length=255)
    images: list[ImageCreate] = Field(min_length=1)
    description: str = Field(min_length=1, max_length=5000)
    category_id: UUID
    slug: Optional[str] = None
    characteristics: Optional[List[CharacteristicCreate]] = []

    model_config = {"from_attributes": True}

class ProductResponse(BaseModel):
    id: UUID
    seller_id: UUID
    category_id: Optional[UUID] = None
    title: str
    slug: str
    images: list[ImageResponse]
    description: str
    status: ProductStatus
    deleted: bool = Field(validation_alias="is_deleted")
    blocking_reason_id: Optional[UUID] = None
    moderator_comment: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    characteristics: List[CharacteristicRead] = []
    skus: List[SKURead]

    model_config = {"from_attributes": True}

class ProductPublicResponse(BaseModel):
    id: UUID
    seller_id: UUID
    category_id: Optional[UUID] = None
    title: str
    slug: str
    images: list[ImageResponse]
    description: str
    status: ProductStatus
    created_at: datetime
    updated_at: datetime
    characteristics: List[CharacteristicRead] = []
    skus: List[SKUPublicResponse] = []

    model_config = {"from_attributes": True}

class ProductUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=5000)
    category_id: Optional[UUID] = None
    characteristics: Optional[List[CharacteristicCreate]] = None

    model_config = {"from_attributes": True}

class ProductDashboardItem(BaseModel):
    id: UUID
    title: str
    images: list[ImageResponse] = Field(default_factory=list)
    status: ProductStatus
    sku_count: int = 0
    published_sku_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class ProductShortResponse(BaseModel):
    id: UUID
    title: str
    slug: str
    status: ProductStatus
    category_id: UUID
    deleted: bool = Field(validation_alias="is_deleted")
    created_at: datetime
    min_price: Optional[int] = None
    cover_image: Optional[str] = None

    model_config = {"from_attributes": True}

class ProductPaginatedResponse(BaseModel):
    items: List[ProductShortResponse] = []
    total_count: int
    limit: int
    offset: int

    model_config = {"from_attributes": True}

class ProductPublicShortResponse(BaseModel):
    id: UUID
    title: str
    slug: str
    status: ProductStatus
    category_id: UUID
    min_price: int
    cover_image: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}

class ProductPublicPaginatedResponse(BaseModel):
    items: List[ProductPublicShortResponse] = []
    total_count: int
    limit: int
    offset: int

    model_config = {"from_attributes": True}

class FieldReport(BaseModel):
    field_name: str
    sku_id: Optional[UUID] = None
    comment: str

class ModerationEventRequest(BaseModel):
    idempotency_key: UUID
    product_id: UUID
    event_type: Literal["MODERATED", "BLOCKED"]
    moderator_id: Optional[UUID] = None
    moderator_comment: Optional[str] = None
    blocking_reason_id: Optional[UUID] = None
    hard_block: bool = False
    field_reports: Optional[List[FieldReport]] = None
    occurred_at: datetime
