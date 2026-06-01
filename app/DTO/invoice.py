from datetime import datetime, timezone
from typing import Optional, List
from sqlmodel import SQLModel
from uuid import UUID
from pydantic import Field

class InvoiceItemCreate(SQLModel):
    sku_id: UUID
    quantity: int = Field(ge=1)

class InvoiceItemRead(SQLModel):
    id: UUID
    sku_id: UUID
    quantity: int
    accepted_quantity: int = 0

    class Config:
        from_attributes = True

class InvoiceItemDetailRead(SQLModel):
    id: UUID
    sku_id: UUID
    quantity: int
    purchase_price: Optional[int] = None
    sku_name: Optional[str] = None
    sku_price: Optional[int] = None

class InvoiceCreate(SQLModel):
    items: List[InvoiceItemCreate] = []

class InvoiceRead(SQLModel):
    id: UUID
    seller_id: UUID
    status: str
    items: List[InvoiceItemRead] = []
    created_at: datetime = datetime.now(timezone.utc)
    updated_at: datetime = datetime.now(timezone.utc)
    accepted_at: Optional[datetime] = None
    accepted_by: Optional[UUID] = None

    class Config:
        from_attributes = True

class InvoicePaginatedResponse(SQLModel):
    items: List[InvoiceRead]
    total_count: int
    limit: int
    offset: int

class InvoiceAcceptRequestItem(SQLModel):
    invoice_item_id: UUID
    accepted_quantity: int = Field(ge=0)

class InvoiceAcceptRequest(SQLModel):
    accepted_items: Optional[List[InvoiceAcceptRequestItem]] = None

class InvoiceDetailRead(SQLModel):
    """
    Детальная информация о накладной для страницы склада.
    Включает полную информацию о позициях с данными SKU.
    """
    id: UUID
    seller_id: UUID
    number: Optional[str] = None
    status: str
    comment: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    items: List[InvoiceItemDetailRead] = []
