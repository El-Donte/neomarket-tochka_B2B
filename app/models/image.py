from typing import Optional, TYPE_CHECKING
from sqlmodel import Field, SQLModel, Relationship
from uuid import UUID
from uuid6 import uuid7
from app.models.product import Product
from sqlalchemy import Column, DateTime
from datetime import datetime, timezone

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.sku import SKU

class Image(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid7, primary_key=True)

    url: str
    ordering: int = 0

    product_id: Optional[UUID] = Field(default=None, foreign_key="products.id")
    sku_id: Optional[UUID] = Field(default=None, foreign_key="skus.id")

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )

    product: Optional["Product"] = Relationship(back_populates="images")
    sku: Optional["SKU"] = Relationship(back_populates="images")