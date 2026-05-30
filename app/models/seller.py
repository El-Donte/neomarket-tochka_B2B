from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey
from sqlmodel import Field, SQLModel, Relationship
from uuid import UUID
from uuid6 import uuid7
from app.models.product import Product

class Seller(SQLModel, table=True):
    __tablename__ = "sellers"
    id: UUID = Field(default_factory=uuid7, primary_key=True)
    first_name: str
    last_name: str
    email: str
    middle_name: Optional[str] = None
    company_name: str
    phone: Optional[str] = None
    password_hash: str
    inn: str
    is_active: bool = Field(default=True)
    is_admin: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True), nullable=False))

    products: List["Product"] = Relationship(back_populates="seller")
