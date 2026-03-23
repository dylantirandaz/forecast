"""Adapter for NYC Department of Buildings (DOB) permit data.

Real data source: NYC Open Data Socrata API
https://data.cityofnewyork.us/Housing-Development/DOB-Permit-Issuance/ipu4-2vj7
"""

import random
from datetime import date, timedelta
from typing import Any

import pandas as pd

from .base import DataAdapter

# Realistic borough-level permit distributions (approximate annual shares)
_BOROUGH_WEIGHTS = {
    "Manhattan": 0.15,
    "Brooklyn": 0.28,
    "Queens": 0.30,
    "Bronx": 0.15,
    "Staten Island": 0.12,
}

_JOB_TYPES = ["NB", "A1", "A2", "A3", "DM", "SG"]
_JOB_TYPE_WEIGHTS = [0.08, 0.35, 0.30, 0.15, 0.05, 0.07]

_BUILDING_TYPES = [
    "Residential",
    "Commercial",
    "Mixed-Use",
    "Industrial",
    "Institutional",
]
_BUILDING_TYPE_WEIGHTS = [0.45, 0.20, 0.20, 0.08, 0.07]

_STATUSES = ["Issued", "In Process", "Withdrawn", "Disapproved"]
_STATUS_WEIGHTS = [0.55, 0.30, 0.10, 0.05]

# ~30k permits/year citywide -> ~2,500/month
_DEFAULT_MONTHLY_COUNT = 2500


class DOBPermitAdapter(DataAdapter):
    """Fetch or generate DOB building permit data."""

    SOURCE_NAME = "nyc_dob_permits"

    REQUIRED_COLUMNS = [
        "permit_id",
        "job_type",
        "filing_date",
        "borough",
        "building_type",
        "units_proposed",
        "status",
    ]

    def __init__(self, *, use_mock: bool = True, api_token: str | None = None):
        self.use_mock = use_mock
        self.api_token = api_token

    # ── public API ────────────────────────────────────────────────────────

    def fetch(self, params: dict[str, Any] | None = None) -> pd.DataFrame:
        if self.use_mock:
            return self._generate_mock(params)
        return self._fetch_live(params)

    def validate(self, data: pd.DataFrame) -> bool:
        missing = set(self.REQUIRED_COLUMNS) - set(data.columns)
        if missing:
            raise ValueError(f"DOB permit data missing columns: {missing}")
        if data.empty:
            raise ValueError("DOB permit DataFrame is empty")
        if data["permit_id"].duplicated().any():
            raise ValueError("Duplicate permit_id values detected")
        return True

    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df["filing_date"] = pd.to_datetime(df["filing_date"])
        df["borough"] = df["borough"].str.strip().str.title()
        df["units_proposed"] = df["units_proposed"].clip(lower=0)
        df["year"] = df["filing_date"].dt.year
        df["month"] = df["filing_date"].dt.month
        return df

    # ── private helpers ───────────────────────────────────────────────────

    def _fetch_live(self, params: dict[str, Any] | None = None) -> pd.DataFrame:
        """Placeholder for real Socrata API call."""
        raise NotImplementedError(
            "Live DOB API fetching not yet implemented. Set use_mock=True."
        )

    def _generate_mock(self, params: dict[str, Any] | None = None) -> pd.DataFrame:
        """Generate realistic mock DOB permit records."""
        params = params or {}
        start = params.get("start_date", date(2018, 1, 1))
        end = params.get("end_date", date(2025, 12, 31))
        monthly_count = params.get("monthly_count", _DEFAULT_MONTHLY_COUNT)

        rng = random.Random(42)
        records: list[dict[str, Any]] = []
        permit_counter = 100_000_000

        current = date(start.year, start.month, 1)
        while current <= end:
            # Seasonal variation: permits dip in winter
            month_factor = 1.0
            if current.month in (12, 1, 2):
                month_factor = 0.75
            elif current.month in (5, 6, 7):
                month_factor = 1.15

            # COVID dip
            if current.year == 2020 and current.month in range(3, 9):
                month_factor *= 0.45

            n = int(monthly_count * month_factor * rng.uniform(0.9, 1.1))

            for _ in range(n):
                borough = rng.choices(
                    list(_BOROUGH_WEIGHTS.keys()),
                    weights=list(_BOROUGH_WEIGHTS.values()),
                )[0]
                job_type = rng.choices(_JOB_TYPES, weights=_JOB_TYPE_WEIGHTS)[0]
                building_type = rng.choices(
                    _BUILDING_TYPES, weights=_BUILDING_TYPE_WEIGHTS
                )[0]
                status = rng.choices(_STATUSES, weights=_STATUS_WEIGHTS)[0]

                # Units proposed: NB (new building) has more units
                if job_type == "NB":
                    if building_type == "Residential":
                        units = max(1, int(rng.gauss(25, 40)))
                    else:
                        units = max(0, int(rng.gauss(5, 10)))
                elif job_type in ("A1", "A2"):
                    units = max(0, int(rng.gauss(2, 5)))
                else:
                    units = 0

                day = rng.randint(1, 28)
                filing = date(current.year, current.month, day)

                records.append(
                    {
                        "permit_id": f"DOB{permit_counter}",
                        "job_type": job_type,
                        "filing_date": filing,
                        "borough": borough,
                        "building_type": building_type,
                        "units_proposed": units,
                        "status": status,
                    }
                )
                permit_counter += 1

            # advance to next month
            if current.month == 12:
                current = date(current.year + 1, 1, 1)
            else:
                current = date(current.year, current.month + 1, 1)

        return pd.DataFrame(records)
