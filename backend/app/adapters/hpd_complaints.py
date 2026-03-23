"""Adapter for NYC HPD (Housing Preservation & Development) complaint data.

Real data source: NYC Open Data
https://data.cityofnewyork.us/Housing-Development/Housing-Maintenance-Code-Complaints/uwyv-629c
"""

import random
from datetime import date
from typing import Any

import pandas as pd

from .base import DataAdapter

_BOROUGH_WEIGHTS = {
    "Bronx": 0.30,
    "Brooklyn": 0.28,
    "Manhattan": 0.20,
    "Queens": 0.15,
    "Staten Island": 0.07,
}

_COMPLAINT_CATEGORIES = [
    "Heat/Hot Water",
    "Plumbing",
    "Paint/Plaster",
    "Elevator",
    "Pest Control",
    "Water Leak",
    "Electric",
    "Door/Window",
    "Safety",
    "General",
    "Appliance",
    "Flooring",
]
_CATEGORY_WEIGHTS = [0.22, 0.15, 0.12, 0.06, 0.10, 0.08, 0.06, 0.05, 0.04, 0.05, 0.04, 0.03]

_STATUSES = ["Open", "Close", "Pending"]
_STATUS_WEIGHTS = [0.25, 0.60, 0.15]

# ~550k complaints per year citywide -> ~46k/month
_DEFAULT_MONTHLY_COUNT = 46_000


class HPDComplaintAdapter(DataAdapter):
    """Fetch or generate HPD housing complaint data."""

    SOURCE_NAME = "nyc_hpd_complaints"

    REQUIRED_COLUMNS = [
        "complaint_id",
        "building_id",
        "borough",
        "date",
        "category",
        "status",
    ]

    def __init__(self, *, use_mock: bool = True, api_token: str | None = None):
        self.use_mock = use_mock
        self.api_token = api_token

    def fetch(self, params: dict[str, Any] | None = None) -> pd.DataFrame:
        if self.use_mock:
            return self._generate_mock(params)
        return self._fetch_live(params)

    def validate(self, data: pd.DataFrame) -> bool:
        missing = set(self.REQUIRED_COLUMNS) - set(data.columns)
        if missing:
            raise ValueError(f"HPD complaint data missing columns: {missing}")
        if data.empty:
            raise ValueError("HPD complaint DataFrame is empty")
        return True

    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df["date"] = pd.to_datetime(df["date"])
        df["borough"] = df["borough"].str.strip().str.title()
        df["year"] = df["date"].dt.year
        df["month"] = df["date"].dt.month
        return df

    # ── private ───────────────────────────────────────────────────────────

    def _fetch_live(self, params: dict[str, Any] | None = None) -> pd.DataFrame:
        raise NotImplementedError(
            "Live HPD API fetching not yet implemented. Set use_mock=True."
        )

    def _generate_mock(self, params: dict[str, Any] | None = None) -> pd.DataFrame:
        params = params or {}
        start = params.get("start_date", date(2018, 1, 1))
        end = params.get("end_date", date(2025, 12, 31))
        monthly_count = params.get("monthly_count", _DEFAULT_MONTHLY_COUNT)

        rng = random.Random(99)
        records: list[dict[str, Any]] = []
        complaint_counter = 7_000_000

        current = date(start.year, start.month, 1)
        while current <= end:
            # Complaints spike in winter (heat complaints)
            if current.month in (11, 12, 1, 2, 3):
                month_factor = 1.35
            elif current.month in (6, 7, 8):
                month_factor = 0.80
            else:
                month_factor = 1.0

            n = int(monthly_count * month_factor * rng.uniform(0.92, 1.08))

            for _ in range(n):
                borough = rng.choices(
                    list(_BOROUGH_WEIGHTS.keys()),
                    weights=list(_BOROUGH_WEIGHTS.values()),
                )[0]
                category = rng.choices(
                    _COMPLAINT_CATEGORIES, weights=_CATEGORY_WEIGHTS
                )[0]
                status = rng.choices(_STATUSES, weights=_STATUS_WEIGHTS)[0]

                # Building IDs: roughly 1M buildings, complaints concentrated
                building_id = rng.randint(1_000_000, 1_200_000)

                day = rng.randint(1, 28)
                complaint_date = date(current.year, current.month, day)

                records.append(
                    {
                        "complaint_id": complaint_counter,
                        "building_id": building_id,
                        "borough": borough,
                        "date": complaint_date,
                        "category": category,
                        "status": status,
                    }
                )
                complaint_counter += 1

            if current.month == 12:
                current = date(current.year + 1, 1, 1)
            else:
                current = date(current.year, current.month + 1, 1)

        return pd.DataFrame(records)
