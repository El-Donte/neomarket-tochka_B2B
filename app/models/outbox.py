from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import Column, DateTime, JSON
from sqlmodel import Field, SQLModel
from uuid6 import uuid7
from enum import Enum


class OutboxStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SENT = "SENT"
    FAILED = "FAILED"

class OutboxEvent(SQLModel, table=True):
    __tablename__ = "outbox_events"

    id: UUID = Field(default_factory=uuid7, primary_key=True)
    destination_service: str = Field(index=True)
    event_type: str
    aggregate_type: str = Field(index=True)
    aggregate_id: UUID = Field(index=True)
    idempotency_key: str = Field(index=True, unique=True)
    payload: Optional[dict] = Field(default_factory=dict, sa_column=Column(JSON))
    
    status: OutboxStatus = Field(default=OutboxStatus.PENDING, index=True)
    retry_count: int = Field(default=0)
    locked_at: Optional[datetime] = Field(
        default=None, 
        sa_column=Column(DateTime(timezone=True), index=True)
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    processed_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
