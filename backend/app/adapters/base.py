"""Abstract base class for all data adapters."""

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class DataAdapter(ABC):
    """Base class that every data adapter must implement.

    Each adapter follows a fetch -> validate -> transform -> ingest pipeline:
      1. fetch()     - pull raw data from API, file, or mock generator
      2. validate()  - check schema, nulls, value ranges
      3. transform() - clean, normalize, derive columns
      4. ingest()    - run the full pipeline and return list of dicts
    """

    SOURCE_NAME: str = "unknown"

    @abstractmethod
    def fetch(self, params: dict[str, Any] | None = None) -> pd.DataFrame:
        """Retrieve raw data as a DataFrame.

        Parameters
        ----------
        params : dict, optional
            Query parameters (date ranges, filters, etc.)

        Returns
        -------
        pd.DataFrame
        """

    @abstractmethod
    def validate(self, data: pd.DataFrame) -> bool:
        """Return True if *data* conforms to expected schema and quality checks.

        Should raise ``ValueError`` with a descriptive message on failure.
        """

    @abstractmethod
    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """Apply cleaning, type coercion, derived columns, etc.

        Returns
        -------
        pd.DataFrame   cleaned/enriched frame ready for storage
        """

    def ingest(self, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Run the full fetch -> validate -> transform pipeline.

        Returns
        -------
        list[dict]   Each dict is one record ready for DB insertion.
        """
        raw = self.fetch(params)
        self.validate(raw)
        clean = self.transform(raw)
        return clean.to_dict(orient="records")
