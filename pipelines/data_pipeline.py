"""End-to-end data pipeline for the NYC Housing Forecasting system.

Orchestrates data ingestion from multiple adapters, preprocessing,
and base-rate computation in a single callable pipeline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Container for the outcome of a pipeline run."""

    records_ingested: int = 0
    records_after_preprocessing: int = 0
    base_rates_computed: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class DataPipeline:
    """Orchestrate the full data lifecycle: ingest, preprocess, compute base rates.

    Parameters
    ----------
    adapter_registry:
        Mapping of adapter names to adapter instances.  Each adapter
        must conform to the :class:`app.adapters.base.DataAdapter`
        interface.
    base_rate_engine:
        An instance of :class:`app.services.base_rate_engine.BaseRateEngine`
        used to compute historical base-rate priors from the processed data.
    """

    def __init__(
        self,
        adapter_registry: dict[str, Any] | None = None,
        base_rate_engine: Any | None = None,
    ) -> None:
        self._adapters: dict[str, Any] = adapter_registry or {}
        self._base_rate_engine = base_rate_engine

    # ------------------------------------------------------------------
    # Stage 1 -- Ingestion
    # ------------------------------------------------------------------

    def run_ingestion(
        self,
        sources: list[str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        """Fetch raw data from all (or selected) adapters and concatenate.

        Parameters
        ----------
        sources:
            List of adapter names to ingest from.  If ``None`` all
            registered adapters are used.
        params:
            Optional query parameters forwarded to each adapter's
            ``fetch()`` call.

        Returns
        -------
        pd.DataFrame
            Combined raw data from all sources.
        """
        adapter_names = sources or list(self._adapters.keys())
        frames: list[pd.DataFrame] = []

        for name in adapter_names:
            adapter = self._adapters.get(name)
            if adapter is None:
                logger.warning("Adapter '%s' not found in registry -- skipping.", name)
                continue
            try:
                logger.info("Ingesting from adapter '%s'...", name)
                records = adapter.ingest(params)
                df = pd.DataFrame(records)
                df["_source"] = name
                frames.append(df)
                logger.info(
                    "Adapter '%s' produced %d records.", name, len(records)
                )
            except Exception:
                logger.exception("Ingestion failed for adapter '%s'.", name)

        if not frames:
            logger.warning("No data ingested from any source.")
            return pd.DataFrame()

        combined = pd.concat(frames, ignore_index=True)
        logger.info("Total raw records ingested: %d", len(combined))
        return combined

    # ------------------------------------------------------------------
    # Stage 2 -- Preprocessing
    # ------------------------------------------------------------------

    def run_preprocessing(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        """Clean, validate, and transform raw ingested data.

        Steps performed:
        1. Drop exact duplicate rows.
        2. Drop rows where all value columns are null.
        3. Forward-fill short gaps within each source group.
        4. Coerce date columns to datetime.

        Parameters
        ----------
        raw_data:
            DataFrame produced by :meth:`run_ingestion`.

        Returns
        -------
        pd.DataFrame
            Cleaned and validated data ready for analysis.
        """
        if raw_data.empty:
            return raw_data

        df = raw_data.copy()

        original_len = len(df)

        # 1. Drop exact duplicates
        df = df.drop_duplicates()
        dupes_dropped = original_len - len(df)
        if dupes_dropped:
            logger.info("Dropped %d duplicate rows.", dupes_dropped)

        # 2. Drop rows with all-null values (excluding metadata columns)
        value_cols = [c for c in df.columns if not c.startswith("_")]
        df = df.dropna(subset=value_cols, how="all")

        # 3. Coerce common date columns
        date_candidates = [c for c in df.columns if "date" in c.lower()]
        for col in date_candidates:
            try:
                df[col] = pd.to_datetime(df[col], errors="coerce")
            except Exception:
                logger.debug("Could not coerce column '%s' to datetime.", col)

        # 4. Sort by date if a date column exists
        if date_candidates:
            primary_date = date_candidates[0]
            df = df.sort_values(primary_date).reset_index(drop=True)

        logger.info(
            "Preprocessing complete: %d -> %d rows.", original_len, len(df)
        )
        return df

    # ------------------------------------------------------------------
    # Stage 3 -- Base-rate computation
    # ------------------------------------------------------------------

    def run_base_rate_computation(
        self,
        processed_data: pd.DataFrame,
        target_metrics: list[str] | None = None,
        geography: str = "nyc",
    ) -> dict[str, Any]:
        """Compute base-rate priors from processed historical data.

        Parameters
        ----------
        processed_data:
            Cleaned DataFrame from :meth:`run_preprocessing`.
        target_metrics:
            Column names in *processed_data* to compute base rates for.
            If ``None`` all numeric columns are used.
        geography:
            Geographic scope label passed to the base-rate engine.

        Returns
        -------
        dict[str, Any]
            Mapping of metric name to its computed
            :class:`~app.services.base_rate_engine.BaseRate` object.
        """
        if self._base_rate_engine is None:
            raise RuntimeError(
                "Cannot compute base rates: no BaseRateEngine provided."
            )

        if processed_data.empty:
            logger.warning("No data available for base-rate computation.")
            return {}

        if target_metrics is None:
            target_metrics = [
                c
                for c in processed_data.select_dtypes(include="number").columns
                if not c.startswith("_")
            ]

        results: dict[str, Any] = {}
        for metric in target_metrics:
            if metric not in processed_data.columns:
                logger.warning("Metric '%s' not found in data -- skipping.", metric)
                continue
            series = processed_data[metric].dropna().values
            if len(series) < 2:
                logger.warning(
                    "Metric '%s' has fewer than 2 observations -- skipping.", metric
                )
                continue
            try:
                base_rate = self._base_rate_engine.compute_base_rate(
                    target_metric=metric,
                    geography=geography,
                    data=series,
                )
                results[metric] = base_rate
                logger.info(
                    "Base rate for '%s': mean=%.4f, trend=%s",
                    metric,
                    base_rate.stats.mean,
                    base_rate.trend.trend_direction if base_rate.trend else "N/A",
                )
            except Exception:
                logger.exception("Base rate computation failed for '%s'.", metric)

        logger.info("Computed base rates for %d metrics.", len(results))
        return results

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------

    def run_full_pipeline(
        self,
        sources: list[str] | None = None,
        params: dict[str, Any] | None = None,
        target_metrics: list[str] | None = None,
        geography: str = "nyc",
    ) -> PipelineResult:
        """Execute the end-to-end data pipeline.

        Runs ingestion, preprocessing, and base-rate computation in
        sequence and returns a summary of the results.

        Parameters
        ----------
        sources:
            Adapter names to ingest from (``None`` = all).
        params:
            Optional parameters forwarded to adapters.
        target_metrics:
            Metrics to compute base rates for (``None`` = all numeric).
        geography:
            Geographic scope for base-rate computation.

        Returns
        -------
        PipelineResult
        """
        result = PipelineResult()

        # Stage 1
        logger.info("=== Stage 1: Ingestion ===")
        raw_data = self.run_ingestion(sources=sources, params=params)
        result.records_ingested = len(raw_data)

        if raw_data.empty:
            result.warnings.append("No data ingested from any source.")
            return result

        # Stage 2
        logger.info("=== Stage 2: Preprocessing ===")
        processed = self.run_preprocessing(raw_data)
        result.records_after_preprocessing = len(processed)

        # Stage 3
        logger.info("=== Stage 3: Base-rate computation ===")
        try:
            base_rates = self.run_base_rate_computation(
                processed,
                target_metrics=target_metrics,
                geography=geography,
            )
            result.base_rates_computed = len(base_rates)
        except RuntimeError as exc:
            msg = str(exc)
            logger.warning("Skipping base-rate stage: %s", msg)
            result.warnings.append(msg)

        logger.info(
            "Pipeline complete: ingested=%d, preprocessed=%d, base_rates=%d",
            result.records_ingested,
            result.records_after_preprocessing,
            result.base_rates_computed,
        )
        return result
