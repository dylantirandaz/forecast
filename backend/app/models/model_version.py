"""ModelVersion model."""

import enum
import uuid
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Boolean, Enum, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseModel

if TYPE_CHECKING:
    from .backtest import BacktestRun
    from .forecast import ForecastRun


class ModelType(str, enum.Enum):
    bayesian_updater = "bayesian_updater"
    ensemble = "ensemble"
    llm_structured = "llm_structured"
    statistical = "statistical"
    hybrid = "hybrid"


class ModelVersion(BaseModel):
    __tablename__ = "model_versions"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    model_type: Mapped[ModelType] = mapped_column(
        Enum(ModelType, name="model_type_enum", create_constraint=True),
        nullable=False,
    )
    config: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    forecast_runs: Mapped[list["ForecastRun"]] = relationship(
        "ForecastRun", back_populates="model_version"
    )
    backtest_runs: Mapped[list["BacktestRun"]] = relationship(
        "BacktestRun", back_populates="model_version"
    )

    def __repr__(self) -> str:
        return f"<ModelVersion(id={self.id}, name='{self.name}', version='{self.version}')>"
