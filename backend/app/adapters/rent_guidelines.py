"""Adapter for NYC Rent Guidelines Board (RGB) historical decisions.

The RGB sets annual allowable rent increases for ~1 million rent-stabilized
apartments.  This dataset is small enough to hardcode from official records.
Source: https://rentguidelinesboard.cityofnewyork.us/
"""

from typing import Any

import pandas as pd

from .base import DataAdapter

# ── Historical RGB decisions (lease years beginning Oct 1) ────────────
# Values are percentage increases.  Negative values = rent decreases.
# Source: RGB annual orders, 2000-2025.
_RGB_HISTORY: list[dict[str, Any]] = [
    {"year": 2000, "one_year_increase": 4.0, "two_year_increase": 6.0},
    {"year": 2001, "one_year_increase": 4.0, "two_year_increase": 6.0},
    {"year": 2002, "one_year_increase": 2.0, "two_year_increase": 4.0},
    {"year": 2003, "one_year_increase": 4.5, "two_year_increase": 7.5},
    {"year": 2004, "one_year_increase": 3.5, "two_year_increase": 6.0},
    {"year": 2005, "one_year_increase": 3.5, "two_year_increase": 5.5},
    {"year": 2006, "one_year_increase": 4.25, "two_year_increase": 7.25},
    {"year": 2007, "one_year_increase": 3.0, "two_year_increase": 5.5},
    {"year": 2008, "one_year_increase": 4.5, "two_year_increase": 8.5},
    {"year": 2009, "one_year_increase": 3.0, "two_year_increase": 5.0},
    {"year": 2010, "one_year_increase": 2.25, "two_year_increase": 4.5},
    {"year": 2011, "one_year_increase": 3.75, "two_year_increase": 7.25},
    {"year": 2012, "one_year_increase": 2.0, "two_year_increase": 4.0},
    {"year": 2013, "one_year_increase": 4.0, "two_year_increase": 7.75},
    {"year": 2014, "one_year_increase": 1.0, "two_year_increase": 2.75},
    {"year": 2015, "one_year_increase": 1.0, "two_year_increase": 2.5},
    {"year": 2016, "one_year_increase": 0.0, "two_year_increase": 2.0},
    {"year": 2017, "one_year_increase": 0.0, "two_year_increase": 2.0},
    {"year": 2018, "one_year_increase": 1.5, "two_year_increase": 2.5},
    {"year": 2019, "one_year_increase": 1.5, "two_year_increase": 2.5},
    {"year": 2020, "one_year_increase": 0.0, "two_year_increase": 0.0},
    {"year": 2021, "one_year_increase": 0.0, "two_year_increase": 0.0},
    {"year": 2022, "one_year_increase": 3.25, "two_year_increase": 5.0},
    {"year": 2023, "one_year_increase": 3.0, "two_year_increase": 2.75},
    {"year": 2024, "one_year_increase": 2.75, "two_year_increase": 5.25},
    {"year": 2025, "one_year_increase": 2.75, "two_year_increase": 5.25},
]


class RGBAdapter(DataAdapter):
    """Provide historical Rent Guidelines Board increase data."""

    SOURCE_NAME = "nyc_rgb"

    REQUIRED_COLUMNS = ["year", "one_year_increase", "two_year_increase"]

    def fetch(self, params: dict[str, Any] | None = None) -> pd.DataFrame:
        """Return the full RGB history (optionally filtered by year range)."""
        params = params or {}
        df = pd.DataFrame(_RGB_HISTORY)

        start_year = params.get("start_year")
        end_year = params.get("end_year")
        if start_year:
            df = df[df["year"] >= start_year]
        if end_year:
            df = df[df["year"] <= end_year]

        return df.reset_index(drop=True)

    def validate(self, data: pd.DataFrame) -> bool:
        missing = set(self.REQUIRED_COLUMNS) - set(data.columns)
        if missing:
            raise ValueError(f"RGB data missing columns: {missing}")
        if data.empty:
            raise ValueError("RGB DataFrame is empty")
        if not data["year"].is_monotonic_increasing:
            raise ValueError("RGB year column is not sorted")
        return True

    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df["year"] = df["year"].astype(int)
        df["one_year_increase"] = df["one_year_increase"].astype(float)
        df["two_year_increase"] = df["two_year_increase"].astype(float)
        # Compute real-value change from baseline (cumulative index)
        df["cumulative_1yr_index"] = (1 + df["one_year_increase"] / 100).cumprod()
        return df
