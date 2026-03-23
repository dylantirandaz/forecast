"""CalibrationRun model for tracking calibration experiments."""

import enum
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Enum, Float, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CalibrationScope(str, enum.Enum):
    global_ = "global"
    domain_specific = "domain_specific"
    target_specific = "target_specific"
    scenario_specific = "scenario_specific"


class CalibrationMethod(str, enum.Enum):
    platt_scaling = "platt_scaling"
    isotonic_regression = "isotonic_regression"
    histogram_binning = "histogram_binning"
    none = "none"


class CalibrationRun(Base):
    """A calibration run tracking pre/post calibration metrics."""

    __tablename__ = "calibration_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    scope: Mapped[CalibrationScope] = mapped_column(
        Enum(
            CalibrationScope,
            name="calibration_scope_enum",
            create_constraint=True,
        ),
        nullable=False,
    )
    domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    target_metric: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    method: Mapped[CalibrationMethod] = mapped_column(
        Enum(
            CalibrationMethod,
            name="calibration_method_enum",
            create_constraint=True,
        ),
        nullable=False,
    )
    n_forecasts: Mapped[int] = mapped_column(Integer, nullable=False)
    pre_calibration_brier: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    post_calibration_brier: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    pre_calibration_log_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    post_calibration_log_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    calibration_params: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )
    bucket_data: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<CalibrationRun(id={self.id}, name='{self.name}', scope={self.scope}, method={self.method})>"
