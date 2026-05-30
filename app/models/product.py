from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING
from sqlmodel import Field, SQLModel, Relationship
from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey
from uuid import UUID
from uuid6 import uuid7
from enum import StrEnum
from sqlalchemy import Enum as SAEnum

from app.models.category import Category

if TYPE_CHECKING:
    from app.models.sku import SKU
    from app.models.seller import Seller
    from app.models.image import Image

class ProductStatus(StrEnum):
    CREATED = "CREATED"
    ON_MODERATION = "ON_MODERATION"
    MODERATED = "MODERATED"
    BLOCKED = "BLOCKED"
    HARD_BLOCKED = "HARD_BLOCKED"

class Product(SQLModel, table=True):
    __tablename__ = "products"
    id: UUID = Field(default_factory=uuid7, primary_key=True)
    seller_id: UUID = Field(foreign_key="sellers.id")
    category_id: Optional[UUID] = Field(default=None, foreign_key="categories.id")
    title: str
    description: Optional[str] = None
    status: ProductStatus = Field(
    sa_column=Column(
        SAEnum(
            ProductStatus,
            native_enum=False,
            values_callable=lambda x: [e.value for e in x]
        ),
        nullable=False,
        default=ProductStatus.CREATED
    )
)
    rating: float = Field(default=0.0)
    orders_count: int = Field(default=0)
    is_deleted: bool = Field(default=False)
    slug: str = Field(index=True, unique=True)
    blocking_reason_id: Optional[UUID] = Field(default=None)
    moderator_comment: Optional[str] = Field(default=None)
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True), nullable=False))
    
    @property
    def min_price(self) -> Optional[int]:
        if not self.skus:
            return None
        return min((sku.price for sku in self.skus), default=None)

    @property
    def cover_image(self) -> Optional[str]:
        if self.images:
            # Return first image by ordering
            sorted_images = sorted(self.images, key=lambda x: x.ordering)
            return sorted_images[0].url
        if self.skus:
            # Fallback to first SKU image
            for sku in self.skus:
                if sku.images:
                    sorted_images = sorted(sku.images, key=lambda x: x.ordering)
                    return sorted_images[0].url
        return None
    
    images: List["Image"] = Relationship(back_populates="product", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    seller: "Seller" = Relationship(back_populates="products")
    category: Optional[Category] = Relationship(back_populates="products")
    skus: List["SKU"] = Relationship(back_populates="product")
