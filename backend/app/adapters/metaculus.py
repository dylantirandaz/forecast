"""Metaculus API adapter for pulling forecasting questions.

Metaculus provides well-structured forecasting questions with community
predictions and resolution criteria. This adapter pulls:
- Currently open binary questions for live forecasting
- Recently resolved questions for backtesting (with contamination caveat)

API docs: https://www.metaculus.com/api2/
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

METACULUS_API_BASE = "https://www.metaculus.com/api2"


@dataclass
class MetaculusQuestion:
    """A question from Metaculus, normalized to our format."""
    id: int
    metaculus_id: int
    title: str
    description: str
    domain: str
    question_type: str  # binary, continuous, multi
    open_date: str  # ISO format
    close_date: str
    resolve_date: str | None
    resolution_criteria: str
    resolved_value: float | None  # None if unresolved
    is_resolved: bool
    community_prediction: float | None  # current community median
    metaculus_prediction: float | None  # Metaculus's own prediction
    url: str
    forecast_cutoff_days: list[int] = field(default_factory=lambda: [90, 30, 7])
    difficulty: str = "medium"
    source_platform: str = "metaculus"
    metadata: dict = field(default_factory=dict)

    def to_eval_format(self) -> dict:
        """Convert to the format expected by run_llm_eval.py."""
        return {
            "id": str(self.id),
            "question_text": self.title,
            "domain": self.domain,
            "question_type": self.question_type,
            "open_date": self.open_date,
            "close_date": self.close_date,
            "resolve_date": self.resolve_date or self.close_date,
            "resolution_criteria": self.resolution_criteria,
            "resolved_value": self.resolved_value if self.resolved_value is not None else -1,
            "forecast_cutoff_days": self.forecast_cutoff_days,
            "difficulty": self.difficulty,
            "source_platform": "metaculus",
            "metaculus_id": self.metaculus_id,
            "community_prediction": self.community_prediction,
            "url": self.url,
        }


class MetaculusAdapter:
    """Adapter for the Metaculus forecasting platform API.

    Usage:
        adapter = MetaculusAdapter()

        # Get open binary questions
        questions = adapter.get_open_questions(question_type="binary", limit=50)

        # Get recently resolved questions (for contaminated backtesting)
        resolved = adapter.get_resolved_questions(limit=50)

        # Get a specific question
        q = adapter.get_question(12345)
    """

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.environ.get("METACULUS_API_KEY", "")
        self.base_url = METACULUS_API_BASE
        self._client = httpx.Client(
            timeout=30.0,
            headers=self._build_headers(),
        )

    def _build_headers(self) -> dict:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Token {self.api_key}"
        return headers

    def get_open_questions(
        self,
        question_type: str = "binary",
        limit: int = 50,
        order_by: str = "-activity",
        search: str = "",
        topic: str = "",
    ) -> list[MetaculusQuestion]:
        """Get currently open questions from Metaculus.

        These are UNCONTAMINATED -- they haven't resolved yet,
        so the LLM can't know the answer from training data.

        Args:
            question_type: "binary", "continuous", or "" for all
            limit: max questions to return
            order_by: sort order. Options: -activity, -publish_time, -close_time
            search: keyword search filter
            topic: filter by topic/tag
        """
        params: dict[str, Any] = {
            "limit": min(limit, 100),
            "offset": 0,
            "status": "open",
            "order_by": order_by,
            "forecast_type": "binary" if question_type == "binary" else "",
            "type": "forecast",
            "include_description": "true",
        }

        if search:
            params["search"] = search
        if topic:
            params["topic"] = topic

        # Remove empty params
        params = {k: v for k, v in params.items() if v}

        questions = []
        fetched = 0

        while fetched < limit:
            params["offset"] = fetched
            params["limit"] = min(100, limit - fetched)

            try:
                resp = self._client.get(f"{self.base_url}/questions/", params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error(f"Metaculus API error: {e}")
                break

            results = data.get("results", [])
            if not results:
                break

            for raw in results:
                q = self._parse_question(raw)
                if q and (not question_type or q.question_type == question_type):
                    questions.append(q)

            fetched += len(results)

            if not data.get("next"):
                break

            time.sleep(0.5)  # rate limiting

        logger.info(f"Fetched {len(questions)} open questions from Metaculus")
        return questions[:limit]

    def get_resolved_questions(
        self,
        question_type: str = "binary",
        limit: int = 50,
        resolved_after: str = "",
    ) -> list[MetaculusQuestion]:
        """Get recently resolved questions.

        WARNING: These may be contaminated if the model was trained
        after their resolution date. Use for framework testing only.

        Args:
            question_type: filter by type
            limit: max questions
            resolved_after: ISO date string, only get questions resolved after this date
        """
        params: dict[str, Any] = {
            "limit": min(limit, 100),
            "status": "resolved",
            "order_by": "-resolve_time",
            "type": "forecast",
            "forecast_type": "binary" if question_type == "binary" else "",
            "include_description": "true",
        }

        if resolved_after:
            params["resolve_time__gt"] = resolved_after

        params = {k: v for k, v in params.items() if v}

        try:
            resp = self._client.get(f"{self.base_url}/questions/", params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"Metaculus API error: {e}")
            return []

        questions = []
        for raw in data.get("results", []):
            q = self._parse_question(raw)
            if q and q.is_resolved:
                questions.append(q)

        logger.info(f"Fetched {len(questions)} resolved questions from Metaculus")
        return questions[:limit]

    def get_question(self, question_id: int) -> MetaculusQuestion | None:
        """Get a single question by Metaculus ID."""
        try:
            resp = self._client.get(f"{self.base_url}/questions/{question_id}/")
            resp.raise_for_status()
            return self._parse_question(resp.json())
        except Exception as e:
            logger.error(f"Failed to fetch question {question_id}: {e}")
            return None

    def _parse_question(self, raw: dict) -> MetaculusQuestion | None:
        """Parse a raw Metaculus API response into our format."""
        try:
            # Determine question type
            q_type = "binary"
            possibilities = raw.get("possibilities", {})
            if possibilities.get("type") == "continuous":
                q_type = "continuous"
            elif possibilities.get("type") == "multiple_choice":
                q_type = "multi"

            # Check if resolved
            resolution = raw.get("resolution")
            is_resolved = resolution is not None and resolution != ""

            # Parse resolution value
            resolved_value = None
            if is_resolved:
                try:
                    resolved_value = float(resolution)
                except (TypeError, ValueError):
                    if resolution in ("yes", "Yes", True):
                        resolved_value = 1.0
                    elif resolution in ("no", "No", False):
                        resolved_value = 0.0
                    elif resolution == "ambiguous":
                        return None  # skip ambiguous resolutions

            # Get community prediction
            community_pred = None
            prediction_data = raw.get("community_prediction", {})
            if isinstance(prediction_data, dict):
                community_pred = prediction_data.get("full", {}).get("q2")  # median
            elif isinstance(prediction_data, (int, float)):
                community_pred = float(prediction_data)

            # Classify domain
            domain = self._classify_domain(raw.get("title", ""), raw.get("description", ""))

            # Estimate difficulty
            difficulty = self._estimate_difficulty(raw)

            # Extract description / resolution criteria
            description = raw.get("description", "") or ""
            resolution_criteria = raw.get("resolution_criteria", "") or description[:500]

            return MetaculusQuestion(
                id=raw.get("id", 0),
                metaculus_id=raw.get("id", 0),
                title=raw.get("title", ""),
                description=description,
                domain=domain,
                question_type=q_type,
                open_date=raw.get("publish_time", raw.get("created_time", "")),
                close_date=raw.get("close_time", ""),
                resolve_date=raw.get("resolve_time"),
                resolution_criteria=resolution_criteria,
                resolved_value=resolved_value,
                is_resolved=is_resolved,
                community_prediction=community_pred,
                metaculus_prediction=raw.get("metaculus_prediction", {}).get("full", {}).get("q2") if isinstance(raw.get("metaculus_prediction"), dict) else None,
                url=f"https://www.metaculus.com/questions/{raw.get('id', 0)}/",
                difficulty=difficulty,
                metadata={
                    "num_predictions": raw.get("number_of_predictions", 0),
                    "author": raw.get("author_name", ""),
                    "tags": [t.get("name", "") for t in raw.get("tags", []) if isinstance(t, dict)],
                },
            )
        except Exception as e:
            logger.warning(f"Failed to parse Metaculus question: {e}")
            return None

    def _classify_domain(self, title: str, description: str) -> str:
        """Classify question domain from title and description."""
        text = (title + " " + description).lower()

        domain_keywords = {
            "macro": ["gdp", "inflation", "cpi", "unemployment", "interest rate", "fed ", "federal reserve", "recession", "economy", "economic"],
            "politics": ["election", "president", "congress", "senate", "vote", "political", "democrat", "republican", "legislation", "governor"],
            "technology": ["ai ", "artificial intelligence", "gpt", "model", "tech", "software", "hardware", "chip", "quantum", "spacex", "launch"],
            "science": ["climate", "vaccine", "study", "research", "scientific", "species", "temperature", "celsius", "discovery"],
            "business": ["company", "stock", "market cap", "revenue", "ipo", "acquisition", "ceo", "profit", "earnings"],
            "housing": ["housing", "rent", "mortgage", "real estate", "zoning", "construction", "permits", "eviction"],
            "geopolitics": ["war", "military", "nato", "china", "russia", "ukraine", "conflict", "sanctions", "treaty"],
            "health": ["covid", "pandemic", "who ", "disease", "mortality", "health", "fda", "drug", "treatment"],
            "energy": ["oil", "opec", "energy", "solar", "nuclear", "renewable", "fossil", "carbon", "emissions"],
        }

        scores = {}
        for domain, keywords in domain_keywords.items():
            scores[domain] = sum(1 for kw in keywords if kw in text)

        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "other"

    def _estimate_difficulty(self, raw: dict) -> str:
        """Estimate question difficulty."""
        num_preds = raw.get("number_of_predictions", 0)

        # More predictions often = higher profile = more info available = easier
        if num_preds > 200:
            return "easy"
        elif num_preds > 50:
            return "medium"
        else:
            return "hard"

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
