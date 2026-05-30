from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class CategoryCreate(BaseModel):
    name: str = Field(..., title="Name", min_length=1, max_length=255)
    parent_id: Optional[UUID] = Field(
        default=None,
        title="Parent Id",
    )

class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(
        default=None,
        title="Name",
    )
    parent_id: Optional[UUID] = Field(
        default=None,
        title="Parent Id",
    )

    is_active: Optional[bool] = Field(
        default=None,
        title="Is active"
    )

class CategoryResponse(BaseModel):
    id: UUID
    name: str
    parent_id: Optional[UUID]
    is_active: bool
    level: int
    path: str
    created_at: datetime

    model_config = {
        "from_attributes": True  # важно для SQLModel
    }

class CategoryWithChildrenResponse(BaseModel):
    id: UUID
    name: str
    parent_id: Optional[UUID]
    is_active: bool
    level: int
    path: str
    created_at: datetime
    children: List[CategoryResponse] = []

    model_config = {
        "from_attributes": True
    }

class CategoryTreeResponse(BaseModel):
    id: UUID
    name: str
    children: List[CategoryTreeResponse] = []

    model_config = {
        "from_attributes": True
    }
