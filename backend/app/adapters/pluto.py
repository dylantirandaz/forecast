"""Adapter for NYC PLUTO (Primary Land Use Tax Lot Output) data.

PLUTO provides lot-level data on land use, building characteristics, and
zoning for every tax lot in NYC (~860k lots).

Source: https://www.nyc.gov/site/planning/data-maps/open-data/dwn-pluto-mappluto.page
"""

import random
from typing import Any

import pandas as pd

from .base import DataAdapter

_BOROUGHS = {
    1: "Manhattan",
    2: "Bronx",
    3: "Brooklyn",
    4: "Queens",
    5: "Staten Island",
}

_LAND_USE_CODES = {
    "01": "One & Two Family Buildings",
    "02": "Multi-Family Walk-Up Buildings",
    "03": "Multi-Family Elevator Buildings",
    "04": "Mixed Residential & Commercial Buildings",
    "05": "Commercial & Office Buildings",
    "06": "Industrial & Manufacturing",
    "07": "Transportation & Utility",
    "08": "Public Facilities & Institutions",
    "09": "Open Space & Outdoor Recreation",
    "10": "Parking Facilities",
    "11": "Vacant Land",
}

# Approximate distributions for residential lots
_ZONING_DISTRICTS = [
    "R1-1", "R2", "R3-1", "R3-2", "R4", "R4-1", "R5",
    "R6", "R6A", "R6B", "R7-1", "R7A", "R7B", "R7D",
    "R8", "R8A", "R8B", "R9", "R10", "C4-4", "C6-2",
    "M1-1", "M1-2",
]

# Borough-level lot counts (approximate)
_BOROUGH_LOT_COUNTS = {
    1: 43_000,   # Manhattan
    2: 91_000,   # Bronx
    3: 280_000,  # Brooklyn
    4: 324_000,  # Queens
    5: 124_000,  # Staten Island
}


class PLUTOAdapter(DataAdapter):
    """Fetch or generate lot-level building data from PLUTO."""

    SOURCE_NAME = "nyc_pluto"

    REQUIRED_COLUMNS = [
        "bbl",
        "borough",
        "block",
        "lot",
        "land_use",
        "res_units",
        "total_units",
        "year_built",
        "num_floors",
        "lot_area_sqft",
        "bldg_area_sqft",
        "zoning_district",
        "assessed_total",
    ]

    def __init__(self, *, use_mock: bool = True, sample_size: int = 5000):
        self.use_mock = use_mock
        self.sample_size = sample_size

    def fetch(self, params: dict[str, Any] | None = None) -> pd.DataFrame:
        if self.use_mock:
            return self._generate_mock(params)
        return self._fetch_live(params)

    def validate(self, data: pd.DataFrame) -> bool:
        missing = set(self.REQUIRED_COLUMNS) - set(data.columns)
        if missing:
            raise ValueError(f"PLUTO data missing columns: {missing}")
        if data.empty:
            raise ValueError("PLUTO DataFrame is empty")
        if data["bbl"].duplicated().any():
            raise ValueError("Duplicate BBL values detected")
        return True

    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df["is_residential"] = df["land_use"].isin(["01", "02", "03", "04"])
        df["is_multifamily"] = df["land_use"].isin(["02", "03"])
        df["far"] = (df["bldg_area_sqft"] / df["lot_area_sqft"].replace(0, 1)).round(2)
        df["building_age"] = 2025 - df["year_built"]
        return df

    # ── private ───────────────────────────────────────────────────────────

    def _fetch_live(self, params: dict[str, Any] | None = None) -> pd.DataFrame:
        raise NotImplementedError(
            "Live PLUTO data fetching not yet implemented. Set use_mock=True."
        )

    def _generate_mock(self, params: dict[str, Any] | None = None) -> pd.DataFrame:
        """Generate a representative sample of PLUTO lot records."""
        params = params or {}
        n = params.get("sample_size", self.sample_size)

        rng = random.Random(55)
        records: list[dict[str, Any]] = []

        for _ in range(n):
            boro_code = rng.choices(
                list(_BOROUGH_LOT_COUNTS.keys()),
                weights=list(_BOROUGH_LOT_COUNTS.values()),
            )[0]
            borough = _BOROUGHS[boro_code]

            block = rng.randint(1, 16_000)
            lot = rng.randint(1, 200)
            bbl = int(f"{boro_code}{block:05d}{lot:04d}")

            # Land use weighted toward residential
            lu_codes = list(_LAND_USE_CODES.keys())
            lu_weights = [0.30, 0.18, 0.10, 0.12, 0.08, 0.04, 0.02, 0.05, 0.03, 0.03, 0.05]
            land_use = rng.choices(lu_codes, weights=lu_weights)[0]

            # Year built
            if land_use in ("01", "02"):
                year_built = rng.choices(
                    [rng.randint(1890, 1930), rng.randint(1930, 1970), rng.randint(1970, 2020)],
                    weights=[0.3, 0.5, 0.2],
                )[0]
            elif land_use == "03":
                year_built = rng.choices(
                    [rng.randint(1950, 1975), rng.randint(1975, 2000), rng.randint(2000, 2024)],
                    weights=[0.35, 0.35, 0.30],
                )[0]
            else:
                year_built = rng.randint(1920, 2024)

            # Residential units
            if land_use == "01":
                res_units = rng.choice([1, 2])
                num_floors = rng.choice([2, 3])
            elif land_use == "02":
                res_units = rng.randint(3, 20)
                num_floors = rng.randint(3, 6)
            elif land_use == "03":
                res_units = rng.randint(20, 300)
                num_floors = rng.randint(6, 40)
            elif land_use == "04":
                res_units = rng.randint(2, 50)
                num_floors = rng.randint(3, 12)
            else:
                res_units = 0
                num_floors = rng.randint(1, 15)

            total_units = res_units + (rng.randint(0, 5) if land_use in ("04", "05") else 0)

            lot_area = rng.randint(1_500, 25_000)
            bldg_area = int(lot_area * rng.uniform(0.5, 4.0) * num_floors / 3)

            zoning = rng.choice(_ZONING_DISTRICTS)

            # Assessed value: rough $/sqft basis
            if borough == "Manhattan":
                psf = rng.uniform(200, 800)
            elif borough in ("Brooklyn", "Queens"):
                psf = rng.uniform(80, 350)
            else:
                psf = rng.uniform(50, 200)
            assessed_total = int(bldg_area * psf)

            records.append(
                {
                    "bbl": bbl,
                    "borough": borough,
                    "block": block,
                    "lot": lot,
                    "land_use": land_use,
                    "res_units": res_units,
                    "total_units": total_units,
                    "year_built": year_built,
                    "num_floors": num_floors,
                    "lot_area_sqft": lot_area,
                    "bldg_area_sqft": bldg_area,
                    "zoning_district": zoning,
                    "assessed_total": assessed_total,
                }
            )

        return pd.DataFrame(records)
