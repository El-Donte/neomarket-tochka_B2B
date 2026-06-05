import uuid
from uuid6 import uuid7
from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import SQLModel, Field


class BlockingReason(SQLModel, table=True):
    __tablename__ = "blocking_reasons"

    id: uuid.UUID = Field(default_factory=uuid7, primary_key=True)
    code: str = Field(max_length=64, unique=True, index=True)
    title: str = Field(max_length=200)
    description: str | None = Field(default=None, sa_type=Text)
    hard_block: bool
    is_active: bool = Field(default=True)