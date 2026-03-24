from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlparse

from forecast.config import SOURCE_QUALITY
from forecast.dates import extract_dates_from_text, parse_date
from forecast.llm import call_llm, parse_llm_json
from forecast.prompts import JUDGE_LEAK_FILTER_PROMPT, QUERY_DECOMPOSITION_PROMPT


@dataclass
class SearchResult:
    source: str
    source_type: str
    source_quality_score: float
    title: str
    content: str
    url: str
    published_at: str


_asknews_api_key: str = ""
_asknews_client_id: str = ""
_asknews_client_secret: str = ""
_search_provider: str = "asknews"
_search_cache: dict[str, list[SearchResult]] = {}


def set_exa_key(key: str) -> None:
    """No-op kept for import compatibility."""


def set_asknews_credentials(
    client_id: str = "",
    client_secret: str = "",
    api_key: str = "",
) -> None:
    global _asknews_api_key, _asknews_client_id, _asknews_client_secret
    _asknews_api_key = api_key
    _asknews_client_id = client_id
    _asknews_client_secret = client_secret


def set_search_provider(provider: str) -> None:
    global _search_provider
    _search_provider = provider


def _resolve_provider() -> str:
    if _search_provider != "auto":
        return _search_provider
    api_key = _asknews_api_key or os.environ.get("ASKNEWS_API_KEY", "")
    if api_key:
        return "asknews"
    an_id = _asknews_client_id or os.environ.get("ASKNEWS_CLIENT_ID", "")
    an_secret = _asknews_client_secret or os.environ.get("ASKNEWS_CLIENT_SECRET", "")
    if an_id and an_secret:
        return "asknews"
    return "none"


# ---------------------------------------------------------------------------
# AskNews provider
# ---------------------------------------------------------------------------

_SEARCH_LOOKBACK_DAYS = 90
_LIVE_SEARCH_HOURS = 24 * 7
_DEFAULT_QUALITY = 0.55


def _search_asknews(
    query: str,
    max_results: int = 5,
    before_date: str | None = None,
) -> list[SearchResult]:
    api_key = _asknews_api_key or os.environ.get("ASKNEWS_API_KEY", "")
    client_id = _asknews_client_id or os.environ.get("ASKNEWS_CLIENT_ID", "")
    client_secret = _asknews_client_secret or os.environ.get("ASKNEWS_CLIENT_SECRET", "")
    if not api_key and (not client_id or not client_secret):
        return []

    try:
        from asknews_sdk import AskNewsSDK
    except ImportError:
        print("  [search] asknews not installed. Run: pip install asknews")
        return []

    try:
        if api_key:
            client = AskNewsSDK(api_key=api_key, scopes=["news"])
        else:
            client = AskNewsSDK(client_id=client_id, client_secret=client_secret, scopes=["news"])

        kwargs: dict = {
            "query": query,
            "n_articles": max_results + 3,
            "method": "both",
            "return_type": "dicts",
            "historical": True,
        }

        if before_date:
            # Use start/end timestamps for precise time-gating.
            # AskNews historical mode returns only articles published
            # within the window — zero outcome leakage by design.
            cutoff_dt = parse_date(before_date)
            kwargs["end_timestamp"] = int(cutoff_dt.timestamp())
            start_dt = cutoff_dt - timedelta(days=_SEARCH_LOOKBACK_DAYS)
            kwargs["start_timestamp"] = int(start_dt.timestamp())
        else:
            kwargs["hours_back"] = _LIVE_SEARCH_HOURS

        response = client.news.search_news(**kwargs)

        results: list[SearchResult] = []
        articles = []
        if hasattr(response, "as_dicts") and response.as_dicts:
            articles = response.as_dicts
        elif hasattr(response, "articles") and response.articles:
            articles = response.articles
        elif isinstance(response, dict):
            articles = response.get("as_dicts") or response.get("articles") or []

        for article in articles:
            if isinstance(article, dict):
                title = article.get("eng_title") or article.get("title") or ""
                content = (article.get("summary") or article.get("eng_summary") or "")[:1500]
                url = article.get("article_url") or article.get("url") or ""
                pub_date = article.get("pub_date") or ""
                source_domain = article.get("source_id") or ""
            else:
                title = getattr(article, "eng_title", "") or getattr(article, "title", "") or ""
                content = (getattr(article, "summary", "") or getattr(article, "eng_summary", "") or "")[:1500]
                url = getattr(article, "article_url", "") or getattr(article, "url", "") or ""
                pub_date = getattr(article, "pub_date", "") or ""
                source_domain = getattr(article, "source_id", "") or ""

            if not source_domain and url:
                try:
                    source_domain = urlparse(url).netloc.replace("www.", "")
                except Exception:
                    source_domain = "unknown"

            quality = _DEFAULT_QUALITY
            for key, score in SOURCE_QUALITY.items():
                if key in source_domain:
                    quality = score
                    break

            source_type = _classify_source_type(source_domain)
            pub_date_str = str(pub_date) if pub_date else ""

            results.append(
                SearchResult(
                    source=source_domain or "unknown",
                    source_type=source_type,
                    source_quality_score=quality,
                    title=title,
                    content=content,
                    url=url,
                    published_at=pub_date_str,
                )
            )

        return results
    except Exception as e:
        print(f"  [search] AskNews search failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Unified search dispatcher
# ---------------------------------------------------------------------------

def search(
    query: str,
    max_results: int = 5,
    before_date: str | None = None,
) -> list[SearchResult]:
    provider = _resolve_provider()
    if provider == "asknews":
        return _search_asknews(query, max_results, before_date)
    print("  [search] No search provider configured (set ASKNEWS_API_KEY or ASKNEWS_CLIENT_ID/SECRET)")
    return []


def _classify_source_type(domain: str) -> str:
    gov_markers = ["gov", "fed", "census", "bls"]
    research_markers = ["arxiv", "nature", "science", "ssrn", "pubmed"]
    if any(m in domain for m in gov_markers):
        return "official_data"
    if any(m in domain for m in research_markers):
        return "research"
    return "news"


# ---------------------------------------------------------------------------
# Judge model — filters outcome leakage from non-news research results
# ---------------------------------------------------------------------------

def judge_filter_leakage(
    results: list[SearchResult],
    question: str,
    cutoff_date: str,
    llm_provider: str = "anthropic",
    judge_model: str = "claude-haiku-4-5-20251001",
) -> list[SearchResult]:
    """Run a judge model over non-news results to strip outcome-leaking info.

    News results from AskNews are already time-gated by end_timestamp, so they
    skip the judge. Non-news results (statistics pages, Wikipedia, historical
    data) go through an LLM that redacts any post-cutoff outcome information
    while preserving useful context like base rates and historical patterns.
    """
    if not results:
        return results

    safe: list[SearchResult] = []
    needs_review: list[SearchResult] = []

    for r in results:
        if r.source_type == "news":
            safe.append(r)
        else:
            needs_review.append(r)

    if not needs_review:
        return safe

    evidence_block = ""
    for i, r in enumerate(needs_review):
        evidence_block += (
            f"--- ITEM {i} ---\n"
            f"Source: {r.source} ({r.source_type})\n"
            f"Title: {r.title}\n"
            f"Content: {r.content}\n\n"
        )

    prompt = JUDGE_LEAK_FILTER_PROMPT.format(
        question=question,
        cutoff_date=cutoff_date,
        evidence=evidence_block,
        n_items=len(needs_review),
    )

    try:
        resp, _, _ = call_llm(
            prompt,
            "You are a temporal information filter. Respond with JSON only.",
            llm_provider,
            judge_model,
            temperature=0.0,
            max_tokens=2000,
        )
        data = parse_llm_json(resp)
        items = data.get("items", [])

        filtered_count = 0
        for item in items:
            idx = item.get("idx", -1)
            if idx < 0 or idx >= len(needs_review):
                continue
            verdict = item.get("verdict", "pass")
            if verdict == "block":
                filtered_count += 1
                continue
            r = needs_review[idx]
            if verdict == "redact":
                cleaned = item.get("cleaned_content", r.content)
                r = SearchResult(
                    source=r.source,
                    source_type=r.source_type,
                    source_quality_score=r.source_quality_score,
                    title=r.title,
                    content=cleaned,
                    url=r.url,
                    published_at=r.published_at,
                )
            safe.append(r)

        if filtered_count > 0:
            print(f"  [judge] Blocked {filtered_count} items for outcome leakage")
        redacted = sum(1 for item in items if item.get("verdict") == "redact")
        if redacted > 0:
            print(f"  [judge] Redacted leaking content from {redacted} items")

    except Exception as e:
        print(f"  [judge] Judge filter failed, falling back to temporal heuristic: {e}")
        for r in needs_review:
            if cutoff_date and has_temporal_leak(r.content, r.title, cutoff_date):
                continue
            safe.append(r)

    return safe


# ---------------------------------------------------------------------------
# Main entry point — search + judge pipeline
# ---------------------------------------------------------------------------

def search_for_question(
    question: str,
    domain: str,
    cutoff_date: str,
    max_results: int = 5,
    provider: str = "anthropic",
    cheap_model: str = "claude-haiku-4-5-20251001",
    use_decomposition: bool = True,
    use_judge: bool = True,
) -> list[SearchResult]:
    cache_key = f"{question[:80]}|{cutoff_date}|{_resolve_provider()}"
    if cache_key in _search_cache:
        return _search_cache[cache_key]

    if use_decomposition:
        queries = decompose_question_into_queries(
            question, domain, cutoff_date, provider, cheap_model,
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

    if use_judge and cutoff_date:
        all_results = judge_filter_leakage(
            all_results, question, cutoff_date,
            llm_provider=provider, judge_model=cheap_model,
        )

    all_results.sort(key=lambda r: r.source_quality_score, reverse=True)
    final = all_results[: max_results * 2]
    search_prov = _resolve_provider()
    print(f"  [search] Found {len(final)} evidence items from {len(queries)} queries ({search_prov})")

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
