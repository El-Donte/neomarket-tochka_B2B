from datetime import datetime, timezone
from typing import Optional
from sqlmodel import Field, SQLModel
from sqlalchemy import Column, DateTime, String, Integer
from uuid import UUID

class IdempotencyKey(SQLModel, table=True):
    __tablename__ = "idempotency_keys"
    
    key: str = Field(primary_key=True)
    response_body: Optional[str] = Field(default=None, sa_column=Column(String, nullable=True))
    response_status_code: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )