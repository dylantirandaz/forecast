"""PolicyEvent model."""

import enum
import uuid
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import Date, DateTime, Enum, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class PolicyEventType(str, enum.Enum):
    legislation = "legislation"
    executive_order = "executive_order"
    regulatory_change = "regulatory_change"
    budget = "budget"
    court_ruling = "court_ruling"


class PolicyEvent(Base):
    __tablename__ = "policy_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_type: Mapped[PolicyEventType] = mapped_column(
        Enum(
            PolicyEventType,
            name="policy_event_type_enum",
            create_constraint=True,
        ),
        nullable=False,
    )
    effective_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    announced_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    jurisdiction: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    affected_targets: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )
    source_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<PolicyEvent(id={self.id}, name='{self.name}')>"
