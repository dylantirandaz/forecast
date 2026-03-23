"""ForecastBench adapter for pulling forecasting questions.

ForecastBench is a standardized benchmark for evaluating forecasting systems.
Questions are stored in a structured format and can be fetched from the
ForecastBench API or GitHub repository.

Reference: https://forecastbench.org
GitHub: https://github.com/forecastingresearch/forecastbench
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

FORECASTBENCH_API = "https://www.forecastbench.org/api"
FORECASTBENCH_GITHUB_RAW = "https://raw.githubusercontent.com/forecastingresearch/forecastbench/main"


@dataclass
class ForecastBenchQuestion:
    """A question from ForecastBench, normalized to our format."""
    id: str
    source_id: str
    title: str
    body: str
    domain: str
    question_type: str  # binary
    created_date: str
    resolution_date: str | None
    resolution_criteria: str
    resolved_value: float | None
    is_resolved: bool
    source: str  # metaculus, polymarket, etc.
    url: str
    difficulty: str = "medium"
    metadata: dict = field(default_factory=dict)

    def to_eval_format(self) -> dict:
        """Convert to the format expected by run_llm_eval.py."""
        return {
            "id": self.id,
            "question_text": self.title,
            "domain": self.domain,
            "question_type": self.question_type,
            "open_date": self.created_date,
            "close_date": self.resolution_date or self.created_date,
            "resolve_date": self.resolution_date or self.created_date,
            "resolution_criteria": self.resolution_criteria,
            "resolved_value": self.resolved_value if self.resolved_value is not None else -1,
            "forecast_cutoff_days": [1],  # ForecastBench uses point-in-time forecasts
            "difficulty": self.difficulty,
            "source_platform": "forecastbench",
            "url": self.url,
        }


class ForecastBenchAdapter:
    """Adapter for ForecastBench forecasting benchmark.

    ForecastBench provides standardized question sets for evaluating
    forecasting systems. Questions come from multiple sources
    (Metaculus, Polymarket, ACLED, etc.) and are curated for quality.

    Usage:
        adapter = ForecastBenchAdapter()

        # Get current open questions
        questions = adapter.get_open_questions(limit=50)

        # Get questions for a specific evaluation round
        questions = adapter.get_round_questions("2025-Q1")

        # Format submission
        submission = adapter.format_submission(forecasts)
    """

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.environ.get("FORECASTBENCH_API_KEY", "")
        self._client = httpx.Client(timeout=30.0)

    def get_open_questions(
        self,
        limit: int = 50,
        source: str = "",
    ) -> list[ForecastBenchQuestion]:
        """Get currently open questions from ForecastBench.

        These are the questions you should forecast for benchmark submission.

        Args:
            limit: max questions to return
            source: filter by source (metaculus, polymarket, etc.)
        """
        try:
            # Try the API first
            params = {"status": "open", "limit": limit}
            if source:
                params["source"] = source

            resp = self._client.get(f"{FORECASTBENCH_API}/questions", params=params)
            resp.raise_for_status()
            data = resp.json()

            questions = []
            for raw in data.get("questions", data if isinstance(data, list) else []):
                q = self._parse_question(raw)
                if q:
                    questions.append(q)

            logger.info(f"Fetched {len(questions)} open questions from ForecastBench API")
            return questions[:limit]

        except Exception as e:
            logger.warning(f"ForecastBench API failed ({e}), trying GitHub fallback")
            return self._fetch_from_github(limit, source)

    def get_resolved_questions(
        self,
        limit: int = 50,
    ) -> list[ForecastBenchQuestion]:
        """Get resolved questions for backtesting."""
        try:
            resp = self._client.get(
                f"{FORECASTBENCH_API}/questions",
                params={"status": "resolved", "limit": limit},
            )
            resp.raise_for_status()
            data = resp.json()

            questions = []
            for raw in data.get("questions", data if isinstance(data, list) else []):
                q = self._parse_question(raw)
                if q and q.is_resolved:
                    questions.append(q)

            return questions[:limit]
        except Exception as e:
            logger.error(f"Failed to fetch resolved questions: {e}")
            return []

    def format_submission(
        self,
        forecasts: list[dict],
        model_name: str = "forecast_engine_v1",
    ) -> dict:
        """Format forecasts for ForecastBench submission.

        Args:
            forecasts: list of dicts with question_id and probability
            model_name: name of your model for the leaderboard

        Returns:
            Submission payload dict
        """
        return {
            "model_name": model_name,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "forecasts": [
                {
                    "question_id": f["question_id"],
                    "probability": round(max(0.01, min(0.99, f["probability"])), 4),
                    "metadata": {
                        "model": f.get("model", model_name),
                        "mode": f.get("mode", "structured"),
                        "cost_usd": f.get("cost", 0),
                    },
                }
                for f in forecasts
            ],
        }

    def _fetch_from_github(self, limit: int, source: str) -> list[ForecastBenchQuestion]:
        """Fallback: fetch question data from GitHub."""
        try:
            # Try to get the question list from GitHub
            resp = self._client.get(
                f"{FORECASTBENCH_GITHUB_RAW}/data/questions.json",
                follow_redirects=True,
            )
            if resp.status_code != 200:
                logger.error(f"GitHub fetch failed: {resp.status_code}")
                return []

            data = resp.json()
            questions = []
            items = data if isinstance(data, list) else data.get("questions", [])

            for raw in items:
                q = self._parse_question(raw)
                if q and (not source or q.source == source):
                    questions.append(q)

            return questions[:limit]
        except Exception as e:
            logger.error(f"GitHub fallback failed: {e}")
            return []

    def _parse_question(self, raw: dict) -> ForecastBenchQuestion | None:
        """Parse a raw question into our format."""
        try:
            title = raw.get("title", raw.get("question", raw.get("question_text", "")))
            if not title:
                return None

            # Determine resolution
            resolution = raw.get("resolution", raw.get("resolved_value"))
            is_resolved = resolution is not None
            resolved_value = None
            if is_resolved:
                try:
                    resolved_value = float(resolution)
                except (TypeError, ValueError):
                    if str(resolution).lower() in ("yes", "true", "1"):
                        resolved_value = 1.0
                    elif str(resolution).lower() in ("no", "false", "0"):
                        resolved_value = 0.0
                    else:
                        return None

            # Classify domain
            text = (title + " " + raw.get("body", raw.get("description", ""))).lower()
            domain = self._classify_domain(text)

            return ForecastBenchQuestion(
                id=str(raw.get("id", raw.get("question_id", ""))),
                source_id=str(raw.get("source_id", raw.get("id", ""))),
                title=title,
                body=raw.get("body", raw.get("description", "")),
                domain=domain,
                question_type=raw.get("question_type", "binary"),
                created_date=raw.get("created_date", raw.get("publish_time", raw.get("created_time", ""))),
                resolution_date=raw.get("resolution_date", raw.get("resolve_time", raw.get("scheduled_resolve_time"))),
                resolution_criteria=raw.get("resolution_criteria", raw.get("body", ""))[:500],
                resolved_value=resolved_value,
                is_resolved=is_resolved,
                source=raw.get("source", raw.get("platform", "unknown")),
                url=raw.get("url", raw.get("question_url", "")),
                metadata=raw.get("metadata", {}),
            )
        except Exception as e:
            logger.warning(f"Failed to parse ForecastBench question: {e}")
            return None

    def _classify_domain(self, text: str) -> str:
        """Same domain classification as Metaculus adapter."""
        domain_keywords = {
            "macro": ["gdp", "inflation", "cpi", "unemployment", "interest rate", "fed ", "recession", "economy"],
            "politics": ["election", "president", "congress", "senate", "vote", "political", "legislation"],
            "technology": ["ai ", "artificial intelligence", "gpt", "tech", "software", "quantum", "spacex"],
            "science": ["climate", "vaccine", "study", "research", "scientific", "temperature"],
            "business": ["company", "stock", "market cap", "revenue", "ipo", "acquisition"],
            "geopolitics": ["war", "military", "nato", "china", "russia", "ukraine", "conflict"],
            "health": ["covid", "pandemic", "disease", "mortality", "health", "fda"],
            "energy": ["oil", "opec", "energy", "solar", "nuclear", "renewable"],
        }
        scores = {d: sum(1 for kw in kws if kw in text) for d, kws in domain_keywords.items()}
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "other"

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
