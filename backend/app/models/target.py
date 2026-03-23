"""Target model."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class TargetCategory(str, enum.Enum):
    supply = "supply"
    price = "price"
    quality = "quality"


class TargetFrequency(str, enum.Enum):
    monthly = "monthly"
    quarterly = "quarterly"
    annual = "annual"


class Target(Base):
    __tablename__ = "targets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[TargetCategory] = mapped_column(
        Enum(
            TargetCategory,
            name="target_category_enum",
            create_constraint=True,
        ),
        nullable=False,
    )
    metric_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(100), nullable=True)
    frequency: Mapped[TargetFrequency] = mapped_column(
        Enum(
            TargetFrequency,
            name="target_frequency_enum",
            create_constraint=True,
        ),
        nullable=False,
    )
    geography: Mapped[str] = mapped_column(
        String(100), default="nyc", nullable=False
    )
    data_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Target(id={self.id}, name='{self.name}', metric_key='{self.metric_key}')>"
