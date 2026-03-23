"""Adapter for Federal Reserve Economic Data (FRED).

Key series for NYC housing forecasting:
  - CPIAUCSL   : CPI-U (All Urban Consumers)
  - UNRATE     : National Unemployment Rate
  - MORTGAGE30US : 30-Year Fixed Mortgage Rate
  - HOUST      : Housing Starts (national, thousands)
  - NYURN      : New York State Unemployment Rate

Real API: https://fred.stlouisfed.org/docs/api/fred/
"""

import random
from datetime import date
from typing import Any

import pandas as pd

from .base import DataAdapter

# ── Realistic baseline values for mock generation ────────────────────
_SERIES_CONFIG = {
    "CPIAUCSL": {
        "description": "Consumer Price Index - All Urban Consumers",
        "base_value": 260.0,  # ~2019 level
        "annual_drift": 0.03,
        "volatility": 0.002,
    },
    "UNRATE": {
        "description": "National Unemployment Rate",
        "base_value": 3.7,
        "annual_drift": 0.0,
        "volatility": 0.15,
    },
    "MORTGAGE30US": {
        "description": "30-Year Fixed Rate Mortgage Average",
        "base_value": 4.0,
        "annual_drift": 0.0,
        "volatility": 0.25,
    },
    "HOUST": {
        "description": "Housing Starts (thousands, seasonally adjusted)",
        "base_value": 1250.0,
        "annual_drift": 0.01,
        "volatility": 30.0,
    },
    "NYURN": {
        "description": "New York State Unemployment Rate",
        "base_value": 4.1,
        "annual_drift": 0.0,
        "volatility": 0.18,
    },
}

# Hardcode a COVID shock for realism
_COVID_OVERRIDES = {
    "UNRATE": {(2020, 4): 14.7, (2020, 5): 13.3, (2020, 6): 11.1, (2020, 7): 10.2},
    "NYURN": {(2020, 4): 15.9, (2020, 5): 14.5, (2020, 6): 12.2, (2020, 7): 11.0},
    "HOUST": {(2020, 4): 891.0, (2020, 5): 1010.0},
}

# Mortgage rate spike 2022-2023
_MORTGAGE_OVERRIDES = {
    (2022, 1): 3.55,
    (2022, 6): 5.81,
    (2022, 10): 7.08,
    (2023, 1): 6.48,
    (2023, 6): 6.71,
    (2023, 10): 7.62,
    (2024, 1): 6.64,
    (2024, 6): 6.92,
    (2025, 1): 6.95,
}


class FREDAdapter(DataAdapter):
    """Fetch or mock-generate FRED macroeconomic time series."""

    SOURCE_NAME = "fred"

    REQUIRED_COLUMNS = ["date", "series_id", "value"]

    def __init__(
        self,
        *,
        use_mock: bool = True,
        api_key: str | None = None,
        series_ids: list[str] | None = None,
    ):
        self.use_mock = use_mock
        self.api_key = api_key
        self.series_ids = series_ids or list(_SERIES_CONFIG.keys())

    def fetch(self, params: dict[str, Any] | None = None) -> pd.DataFrame:
        if self.use_mock:
            return self._generate_mock(params)
        return self._fetch_live(params)

    def validate(self, data: pd.DataFrame) -> bool:
        missing = set(self.REQUIRED_COLUMNS) - set(data.columns)
        if missing:
            raise ValueError(f"FRED data missing columns: {missing}")
        if data.empty:
            raise ValueError("FRED DataFrame is empty")
        return True

    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df["date"] = pd.to_datetime(df["date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.sort_values(["series_id", "date"]).reset_index(drop=True)
        return df

    # ── private ───────────────────────────────────────────────────────────

    def _fetch_live(self, params: dict[str, Any] | None = None) -> pd.DataFrame:
        raise NotImplementedError(
            "Live FRED API fetching not yet implemented. Set use_mock=True."
        )

    def _generate_mock(self, params: dict[str, Any] | None = None) -> pd.DataFrame:
        params = params or {}
        start = params.get("start_date", date(2015, 1, 1))
        end = params.get("end_date", date(2025, 12, 31))

        rng = random.Random(77)
        records: list[dict[str, Any]] = []

        for sid in self.series_ids:
            cfg = _SERIES_CONFIG.get(sid)
            if cfg is None:
                continue

            value = cfg["base_value"]
            current = date(start.year, start.month, 1)

            while current <= end:
                key = (current.year, current.month)

                # Apply overrides for known events
                overrides = _COVID_OVERRIDES.get(sid, {})
                if key in overrides:
                    value = overrides[key]
                elif sid == "MORTGAGE30US" and key in _MORTGAGE_OVERRIDES:
                    value = _MORTGAGE_OVERRIDES[key]
                else:
                    monthly_drift = cfg["annual_drift"] / 12
                    noise = rng.gauss(0, cfg["volatility"])
                    value = value * (1 + monthly_drift) + noise

                # Clamp non-negative for rates
                if sid in ("UNRATE", "NYURN", "MORTGAGE30US"):
                    value = max(0.1, value)

                records.append(
                    {
                        "date": current,
                        "series_id": sid,
                        "value": round(value, 2),
                    }
                )

                if current.month == 12:
                    current = date(current.year + 1, 1, 1)
                else:
                    current = date(current.year, current.month + 1, 1)

        return pd.DataFrame(records)
