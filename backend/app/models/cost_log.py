"""CostLog model for tracking API and compute costs."""

import enum
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Enum, Float, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class OperationType(str, enum.Enum):
    forecast_run = "forecast_run"
    evidence_scoring = "evidence_scoring"
    base_rate_compute = "base_rate_compute"
    backtest_run = "backtest_run"
    experiment_run = "experiment_run"
    llm_call = "llm_call"
    data_ingestion = "data_ingestion"


class CostLog(Base):
    """Individual cost log entry for tracking API and compute spend."""

    __tablename__ = "cost_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    operation_type: Mapped[OperationType] = mapped_column(
        Enum(
            OperationType,
            name="operation_type_enum",
            create_constraint=True,
        ),
        nullable=False,
    )
    reference_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    reference_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    model_tier: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    metadata_: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<CostLog(id={self.id}, op={self.operation_type}, cost=${self.cost_usd:.4f})>"
