"""
Cached web-search service that sits between the workspace and whatever
`app.search` provider is configured.

- Caching: identical (provider, max_results, query) lookups within the TTL are
  served from an in-process cache, so re-running research on a topic — or two
  companies researching the same thing — doesn't re-bill the search API. Web
  results are public, so a shared query cache is correct and never leaks
  company-private data (the *sources* land in each company's own workspace
  session; only the raw public results are shared).
- Attribution: `to_sources()` turns results into the Sources-panel shape with
  `derived=False`, marking them as real retrieved pages.

Swapping the provider never touches this module — it only talks to
`app.search.factory`.
"""
from __future__ import annotations

import time

from app.config import settings
from app.logging_config import get_logger
from app.search.factory import get_search_provider

logger = get_logger(__name__)

# (provider, max_results, normalized-query) -> (stored_at, results-as-dicts)
_CACHE: dict[str, tuple[float, list[dict]]] = {}


def _key(provider: str, query: str, max_results: int) -> str:
    return f"{provider}:{max_results}:{' '.join(query.lower().split())}"


async def search(query: str, *, max_results: int | None = None, ttl: int | None = None) -> dict:
    """Run (or serve from cache) a web search.

    Returns ``{configured, provider, cached, results}`` — always safe to call;
    when no provider is configured it returns ``configured=False`` with empty
    results so Deep Research can fall back to model-knowledge mode.
    """
    provider = get_search_provider()
    if provider is None:
        return {"configured": False, "provider": None, "cached": False, "results": []}

    q = (query or "").strip()
    if not q:
        return {"configured": True, "provider": provider.name, "cached": False, "results": []}

    max_results = max_results or settings.SEARCH_MAX_RESULTS
    ttl = settings.SEARCH_CACHE_TTL_SECONDS if ttl is None else ttl
    key = _key(provider.name, q, max_results)
    now = time.time()

    hit = _CACHE.get(key)
    if hit and (now - hit[0]) < ttl:
        return {"configured": True, "provider": provider.name, "cached": True, "results": hit[1]}

    results = await provider.search(q, max_results=max_results)
    serialized = [r.as_dict() for r in results]
    _CACHE[key] = (now, serialized)
    logger.info("web_search", provider=provider.name, query=q, count=len(serialized))
    return {"configured": True, "provider": provider.name, "cached": False, "results": serialized}


def to_sources(results: list[dict]) -> list[dict]:
    """Turn raw result dicts into workspace Source records (derived=False)."""
    from app.search.base import SearchResult

    sources = []
    for i, r in enumerate(results, 1):
        sr = SearchResult(
            title=r.get("title", ""),
            url=r.get("url", ""),
            snippet=r.get("snippet", ""),
            source=r.get("source", ""),
            published=r.get("published"),
            score=r.get("score"),
        )
        sources.append(sr.as_source(f"s{i}"))
    return sources


def cache_clear() -> None:
    _CACHE.clear()


def cache_size() -> int:
    return len(_CACHE)
