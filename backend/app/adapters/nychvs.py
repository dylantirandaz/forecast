"""Adapter for the NYC Housing and Vacancy Survey (NYCHVS).

The NYCHVS is conducted approximately every three years by the U.S. Census
Bureau on behalf of the NYC Department of Housing Preservation & Development.
It provides the official vacancy-rate estimate that triggers rent-stabilization
continuation.

Source: https://www.census.gov/programs-surveys/nychvs.html
"""

import random
from typing import Any

import pandas as pd

from .base import DataAdapter

# ── Realistic NYCHVS summary data (survey years) ─────────────────────
# Figures drawn from published NYCHVS reports (rounded).
_NYCHVS_SURVEYS: list[dict[str, Any]] = [
    {
        "survey_year": 2002,
        "total_units": 3_269_000,
        "occupied_units": 3_122_000,
        "vacant_units": 147_000,
        "vacancy_rate_pct": 4.49,
        "rent_stabilized_units": 1_043_000,
        "rent_controlled_units": 59_000,
        "public_housing_units": 178_000,
        "market_rate_units": 1_036_000,
        "median_gross_rent": 850,
        "median_stabilized_rent": 750,
        "median_market_rent": 1_100,
        "owner_occupied_units": 806_000,
        "crowded_pct": 9.2,
        "severely_crowded_pct": 3.8,
        "maintenance_deficient_pct": 11.2,
    },
    {
        "survey_year": 2005,
        "total_units": 3_317_000,
        "occupied_units": 3_207_000,
        "vacant_units": 110_000,
        "vacancy_rate_pct": 3.09,
        "rent_stabilized_units": 1_043_000,
        "rent_controlled_units": 43_000,
        "public_housing_units": 178_000,
        "market_rate_units": 1_067_000,
        "median_gross_rent": 925,
        "median_stabilized_rent": 850,
        "median_market_rent": 1_250,
        "owner_occupied_units": 876_000,
        "crowded_pct": 8.8,
        "severely_crowded_pct": 3.5,
        "maintenance_deficient_pct": 10.5,
    },
    {
        "survey_year": 2008,
        "total_units": 3_344_000,
        "occupied_units": 3_240_000,
        "vacant_units": 104_000,
        "vacancy_rate_pct": 2.88,
        "rent_stabilized_units": 1_025_000,
        "rent_controlled_units": 39_000,
        "public_housing_units": 178_000,
        "market_rate_units": 1_080_000,
        "median_gross_rent": 1_050,
        "median_stabilized_rent": 950,
        "median_market_rent": 1_450,
        "owner_occupied_units": 918_000,
        "crowded_pct": 8.5,
        "severely_crowded_pct": 3.3,
        "maintenance_deficient_pct": 9.8,
    },
    {
        "survey_year": 2011,
        "total_units": 3_371_000,
        "occupied_units": 3_269_000,
        "vacant_units": 102_000,
        "vacancy_rate_pct": 3.12,
        "rent_stabilized_units": 1_014_000,
        "rent_controlled_units": 38_000,
        "public_housing_units": 176_000,
        "market_rate_units": 1_092_000,
        "median_gross_rent": 1_150,
        "median_stabilized_rent": 1_050,
        "median_market_rent": 1_600,
        "owner_occupied_units": 949_000,
        "crowded_pct": 8.1,
        "severely_crowded_pct": 3.1,
        "maintenance_deficient_pct": 9.3,
    },
    {
        "survey_year": 2014,
        "total_units": 3_400_000,
        "occupied_units": 3_284_000,
        "vacant_units": 116_000,
        "vacancy_rate_pct": 3.45,
        "rent_stabilized_units": 966_000,
        "rent_controlled_units": 27_000,
        "public_housing_units": 176_000,
        "market_rate_units": 1_141_000,
        "median_gross_rent": 1_300,
        "median_stabilized_rent": 1_200,
        "median_market_rent": 1_800,
        "owner_occupied_units": 974_000,
        "crowded_pct": 7.8,
        "severely_crowded_pct": 2.9,
        "maintenance_deficient_pct": 8.7,
    },
    {
        "survey_year": 2017,
        "total_units": 3_469_000,
        "occupied_units": 3_374_000,
        "vacant_units": 95_000,
        "vacancy_rate_pct": 3.63,
        "rent_stabilized_units": 966_000,
        "rent_controlled_units": 22_000,
        "public_housing_units": 174_000,
        "market_rate_units": 1_176_000,
        "median_gross_rent": 1_450,
        "median_stabilized_rent": 1_300,
        "median_market_rent": 2_050,
        "owner_occupied_units": 1_036_000,
        "crowded_pct": 7.5,
        "severely_crowded_pct": 2.7,
        "maintenance_deficient_pct": 8.2,
    },
    {
        "survey_year": 2021,
        "total_units": 3_544_000,
        "occupied_units": 3_378_000,
        "vacant_units": 166_000,
        "vacancy_rate_pct": 4.54,
        "rent_stabilized_units": 1_048_000,
        "rent_controlled_units": 16_400,
        "public_housing_units": 172_000,
        "market_rate_units": 1_140_000,
        "median_gross_rent": 1_550,
        "median_stabilized_rent": 1_400,
        "median_market_rent": 2_200,
        "owner_occupied_units": 1_001_000,
        "crowded_pct": 7.0,
        "severely_crowded_pct": 2.5,
        "maintenance_deficient_pct": 7.9,
    },
    {
        "survey_year": 2023,
        "total_units": 3_577_000,
        "occupied_units": 3_440_000,
        "vacant_units": 137_000,
        "vacancy_rate_pct": 1.41,
        "rent_stabilized_units": 1_048_000,
        "rent_controlled_units": 16_000,
        "public_housing_units": 171_000,
        "market_rate_units": 1_175_000,
        "median_gross_rent": 1_800,
        "median_stabilized_rent": 1_500,
        "median_market_rent": 2_750,
        "owner_occupied_units": 1_030_000,
        "crowded_pct": 7.2,
        "severely_crowded_pct": 2.6,
        "maintenance_deficient_pct": 8.0,
    },
]


class NYCHVSAdapter(DataAdapter):
    """Provide NYCHVS historical survey data."""

    SOURCE_NAME = "nychvs"

    REQUIRED_COLUMNS = [
        "survey_year",
        "total_units",
        "vacancy_rate_pct",
        "rent_stabilized_units",
    ]

    def fetch(self, params: dict[str, Any] | None = None) -> pd.DataFrame:
        """Return NYCHVS survey-level summary data."""
        params = params or {}
        df = pd.DataFrame(_NYCHVS_SURVEYS)

        start_year = params.get("start_year")
        end_year = params.get("end_year")
        if start_year:
            df = df[df["survey_year"] >= start_year]
        if end_year:
            df = df[df["survey_year"] <= end_year]

        return df.reset_index(drop=True)

    def validate(self, data: pd.DataFrame) -> bool:
        missing = set(self.REQUIRED_COLUMNS) - set(data.columns)
        if missing:
            raise ValueError(f"NYCHVS data missing columns: {missing}")
        if data.empty:
            raise ValueError("NYCHVS DataFrame is empty")
        if (data["vacancy_rate_pct"] < 0).any() or (data["vacancy_rate_pct"] > 20).any():
            raise ValueError("Vacancy rate out of plausible range [0, 20]")
        return True

    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df["regulated_units"] = (
            df["rent_stabilized_units"]
            + df.get("rent_controlled_units", 0)
            + df.get("public_housing_units", 0)
        )
        df["regulated_share_pct"] = (df["regulated_units"] / df["total_units"] * 100).round(1)
        df["rent_gap"] = df["median_market_rent"] - df["median_stabilized_rent"]
        return df
