import uuid
from uuid6 import uuid7
from sqlalchemy import String, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BlockingReason(Base):
    __tablename__ = "blocking_reasons"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid7,
    )

    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    title: Mapped[str] = mapped_column(String(200))

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    hard_block: Mapped[bool] = mapped_column(Boolean)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)