"""Search adapters for retrieving evidence from the web.

Supports:
- Exa.ai (primary) -- neural search with content extraction
- Fallback: no-op adapter that returns empty results
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single search result."""
    title: str
    url: str
    content: str
    published_at: str  # ISO format
    source: str
    source_type: str = "news"
    source_quality_score: float = 0.6
    score: float = 0.0  # search relevance score
    metadata: dict = field(default_factory=dict)


class ExaSearchAdapter:
    """Search adapter using Exa.ai for neural search.

    Exa provides high-quality search results with content extraction,
    which is ideal for evidence gathering in forecasting.
    """

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.environ.get("EXA_API_KEY", "")
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self.api_key:
            raise RuntimeError("EXA_API_KEY not set. Set it in .env or pass to constructor.")
        try:
            from exa_py import Exa
            self._client = Exa(api_key=self.api_key)
            return self._client
        except ImportError:
            raise RuntimeError("pip install exa-py")

    def search(
        self,
        query: str,
        num_results: int = 5,
        start_date: str | None = None,
        end_date: str | None = None,
        domains: list[str] | None = None,
        category: str | None = None,
    ) -> list[SearchResult]:
        """Search for evidence using Exa.ai.

        Args:
            query: Search query
            num_results: Max results to return
            start_date: Only results published after this date (ISO format)
            end_date: Only results published before this date (for temporal integrity)
            domains: Restrict to specific domains (e.g. ["reuters.com", "bls.gov"])
            category: Exa category filter (e.g. "news", "research paper")
        """
        client = self._get_client()

        kwargs: dict[str, Any] = {
            "query": query,
            "num_results": num_results,
            "type": "neural",
            "use_autoprompt": True,
            "text": {"max_characters": 1500},  # get content
        }

        if start_date:
            kwargs["start_published_date"] = start_date
        if end_date:
            kwargs["end_published_date"] = end_date
        if domains:
            kwargs["include_domains"] = domains
        if category:
            kwargs["category"] = category

        try:
            response = client.search_and_contents(**kwargs)
        except Exception as e:
            logger.error(f"Exa search failed: {e}")
            return []

        results = []
        for r in response.results:
            # Determine source quality based on domain
            domain = self._extract_domain(r.url)
            quality = self._estimate_source_quality(domain)
            source_type = self._classify_source_type(domain)

            published = r.published_date or datetime.now(timezone.utc).isoformat()

            results.append(SearchResult(
                title=r.title or "",
                url=r.url,
                content=r.text or "",
                published_at=published,
                source=domain,
                source_type=source_type,
                source_quality_score=quality,
                score=r.score if hasattr(r, "score") else 0.0,
                metadata={"autoprompt_query": getattr(r, "autoprompt_string", None)},
            ))

        logger.info(f"Exa search returned {len(results)} results for: {query[:80]}")
        return results

    def search_for_question(
        self,
        question_text: str,
        domain: str = "",
        cutoff_date: str | None = None,
        num_results: int = 5,
    ) -> list[SearchResult]:
        """Search for evidence relevant to a forecasting question.

        Generates targeted queries and enforces temporal integrity
        by limiting results to before the cutoff date.
        """
        queries = self._generate_queries(question_text, domain)

        all_results: list[SearchResult] = []
        seen_urls: set[str] = set()

        for query in queries[:3]:  # max 3 sub-queries
            results = self.search(
                query=query,
                num_results=num_results,
                end_date=cutoff_date,
                category="news",
            )
            for r in results:
                if r.url not in seen_urls:
                    seen_urls.add(r.url)
                    all_results.append(r)

        # Sort by relevance score
        all_results.sort(key=lambda r: r.score, reverse=True)
        return all_results[:num_results * 2]  # return up to 2x requested

    def _generate_queries(self, question_text: str, domain: str) -> list[str]:
        """Generate search queries from a forecasting question."""
        # The question itself is often a good query
        queries = [question_text]

        # Add domain-specific query
        if domain:
            queries.append(f"{domain} {question_text}")

        # Extract key terms for a more targeted query
        # Simple: take the first part before "?"
        if "?" in question_text:
            core = question_text.split("?")[0]
            queries.append(core)

        return queries

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            return urlparse(url).netloc.replace("www.", "")
        except Exception:
            return "unknown"

    def _estimate_source_quality(self, domain: str) -> float:
        """Estimate source quality based on domain."""
        HIGH_QUALITY: dict[str, float] = {
            "reuters.com": 0.95, "apnews.com": 0.95, "bls.gov": 0.98,
            "fred.stlouisfed.org": 0.98, "census.gov": 0.97,
            "federalreserve.gov": 0.98, "nature.com": 0.95,
            "science.org": 0.95, "nejm.org": 0.95,
            "economist.com": 0.88, "ft.com": 0.88,
            "bloomberg.com": 0.87, "wsj.com": 0.87,
            "nytimes.com": 0.82, "washingtonpost.com": 0.82,
            "bbc.com": 0.85, "bbc.co.uk": 0.85,
            "arxiv.org": 0.80, "ssrn.com": 0.78,
        }
        for key, score in HIGH_QUALITY.items():
            if key in domain:
                return score
        return 0.55  # default for unknown sources

    def _classify_source_type(self, domain: str) -> str:
        """Classify source type from domain."""
        GOV = {"gov", "fed", "census", "bls", "noaa", "nih"}
        RESEARCH = {"arxiv", "ssrn", "nature", "science", "nejm", "pubmed", "springer"}

        dl = domain.lower()
        if any(g in dl for g in GOV):
            return "official_data"
        if any(r in dl for r in RESEARCH):
            return "research"
        return "news"


class NoOpSearchAdapter:
    """Fallback search adapter that returns empty results.

    Used when no search API key is configured.
    """

    def search(self, query: str, **kwargs) -> list[SearchResult]:
        return []

    def search_for_question(self, question_text: str, **kwargs) -> list[SearchResult]:
        return []


def get_search_adapter() -> ExaSearchAdapter | NoOpSearchAdapter:
    """Get the appropriate search adapter based on configuration."""
    exa_key = os.environ.get("EXA_API_KEY", "")
    if exa_key:
        return ExaSearchAdapter(api_key=exa_key)
    logger.warning("No EXA_API_KEY set. Search will return empty results.")
    return NoOpSearchAdapter()
