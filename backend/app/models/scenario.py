"""Scenario model."""

import enum
import uuid
from datetime import date
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Date, Enum, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseModel

if TYPE_CHECKING:
    from .forecast import ForecastRun


class ScenarioIntensity(str, enum.Enum):
    soft = "soft"
    moderate = "moderate"
    aggressive = "aggressive"


class Scenario(BaseModel):
    __tablename__ = "scenarios"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    narrative: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assumptions: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    policy_levers: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )
    timing_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    timing_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    intensity: Mapped[Optional[ScenarioIntensity]] = mapped_column(
        Enum(
            ScenarioIntensity,
            name="scenario_intensity_enum",
            create_constraint=True,
        ),
        nullable=True,
    )
    expected_channels: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )

    # Relationships
    forecast_runs: Mapped[list["ForecastRun"]] = relationship(
        "ForecastRun", back_populates="scenario"
    )

    def __repr__(self) -> str:
        return f"<Scenario(id={self.id}, name='{self.name}')>"
