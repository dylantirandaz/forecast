from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse

from forecast.config import SOURCE_QUALITY
from forecast.dates import extract_dates_from_text, parse_date
from forecast.llm import call_llm, parse_llm_json
from forecast.prompts import QUERY_DECOMPOSITION_PROMPT


@dataclass
class SearchResult:
    source: str
    source_type: str
    source_quality_score: float
    title: str
    content: str
    url: str
    published_at: str


_exa_api_key: str = ""
_search_cache: dict[str, list[SearchResult]] = {}


def set_exa_key(key: str) -> None:
    global _exa_api_key
    _exa_api_key = key


def search(
    query: str,
    max_results: int = 5,
    before_date: str | None = None,
) -> list[SearchResult]:
    api_key = _exa_api_key or os.environ.get("EXA_API_KEY", "")
    if not api_key:
        return []

    try:
        from exa_py import Exa
    except ImportError:
        print("  [search] exa-py not installed. Run: pip install exa-py")
        return []

    try:
        client = Exa(api_key=api_key)
        kwargs: dict = {
            "query": query,
            "num_results": max_results + 3,
            "type": "neural",
            "text": {"max_characters": 1500},
        }
        if before_date:
            kwargs["end_published_date"] = before_date

        response = client.search_and_contents(**kwargs)
        results: list[SearchResult] = []
        filtered_count = 0

        for r in response.results:
            title = r.title or ""
            content = (r.text or "")[:1500]

            if before_date and r.published_date:
                try:
                    if parse_date(r.published_date) > parse_date(before_date):
                        filtered_count += 1
                        continue
                except Exception:
                    pass

            if before_date and has_temporal_leak(content, title, before_date):
                filtered_count += 1
                continue

            domain = ""
            try:
                domain = urlparse(r.url).netloc.replace("www.", "")
            except Exception:
                pass

            quality = 0.55
            for key, score in SOURCE_QUALITY.items():
                if key in domain:
                    quality = score
                    break

            source_type = _classify_source_type(domain)

            results.append(
                SearchResult(
                    source=domain or "unknown",
                    source_type=source_type,
                    source_quality_score=quality,
                    title=title,
                    content=content,
                    url=r.url,
                    published_at=r.published_date or "",
                )
            )

        if filtered_count > 0:
            print(f"  [search] Filtered {filtered_count} results for temporal leakage")

        return results
    except Exception as e:
        print(f"  [search] Exa search failed: {e}")
        return []


def _classify_source_type(domain: str) -> str:
    gov_markers = ["gov", "fed", "census", "bls"]
    research_markers = ["arxiv", "nature", "science", "ssrn", "pubmed"]
    if any(m in domain for m in gov_markers):
        return "official_data"
    if any(m in domain for m in research_markers):
        return "research"
    return "news"


def search_for_question(
    question: str,
    domain: str,
    cutoff_date: str,
    max_results: int = 5,
    provider: str = "anthropic",
    cheap_model: str = "claude-haiku-4-5-20251001",
    use_decomposition: bool = True,
) -> list[SearchResult]:
    cache_key = f"{question[:80]}|{cutoff_date}"
    if cache_key in _search_cache:
        return _search_cache[cache_key]

    if use_decomposition:
        queries = decompose_question_into_queries(
            question,
            domain,
            cutoff_date,
            provider,
            cheap_model,
        )
        print(f"  [search] Decomposed into {len(queries)} queries: {[q[:50] for q in queries]}")
    else:
        queries = [question]
        if "?" in question:
            core = question.split("?")[0].strip()
            if len(core) > 20:
                queries.append(core)

    all_results: list[SearchResult] = []
    seen_urls: set[str] = set()

    for q in queries:
        results = search(q, max_results=max_results, before_date=cutoff_date)
        for r in results:
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                all_results.append(r)

    all_results.sort(key=lambda r: r.source_quality_score, reverse=True)
    final = all_results[: max_results * 2]
    print(f"  [search] Found {len(final)} evidence items from {len(queries)} queries")

    _search_cache[cache_key] = final
    return final


def has_temporal_leak(content: str, title: str, cutoff_date: str) -> bool:
    try:
        cutoff = parse_date(cutoff_date)
    except Exception:
        return False

    text = title + " " + content
    mentioned_dates = extract_dates_from_text(text)

    future_count = 0
    for date_str in mentioned_dates:
        try:
            if parse_date(date_str) > cutoff:
                future_count += 1
        except Exception:
            continue

    if mentioned_dates and future_count > len(mentioned_dates) * 0.5:
        return True

    future_phrases = [
        "was released",
        "was announced",
        "reached an all-time",
        "hit a record",
        "breached",
        "surpassed",
    ]
    text_lower = text.lower()
    for phrase in future_phrases:
        if phrase in text_lower and future_count > 0:
            return True

    return False


def decompose_question_into_queries(
    question: str,
    domain: str,
    cutoff_date: str,
    provider: str,
    model: str,
) -> list[str]:
    prompt = QUERY_DECOMPOSITION_PROMPT.format(
        question=question,
        domain=domain,
        cutoff_date=cutoff_date,
    )
    try:
        resp, _, _ = call_llm(
            prompt,
            "You are a research assistant. Respond with JSON only.",
            provider,
            model,
            temperature=0.3,
        )
        data = parse_llm_json(resp)
        queries = data.get("queries", [])
        if queries:
            return queries[:5]
    except Exception as e:
        print(f"  [decompose] Query decomposition failed: {e}")

    queries = [question]
    if "?" in question:
        core = question.split("?")[0].strip()
        if len(core) > 20:
            queries.append(core)
    return queries
