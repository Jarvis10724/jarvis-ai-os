"""
Tavily web-search provider (https://tavily.com) — the default live provider.

Chosen because it returns clean, ranked results with content snippets from a
single JSON endpoint, which maps directly onto `SearchResult`. Requires
`TAVILY_API_KEY`; when unset the provider reports `configured=False` and the
factory hands back None so Deep Research degrades to its honest
model-knowledge mode.
"""
from __future__ import annotations

import httpx

from app.config import settings
from app.exceptions import IntegrationError
from app.search.base import BaseSearchProvider, SearchResult

_ENDPOINT = "https://api.tavily.com/search"


class TavilyProvider(BaseSearchProvider):
    name = "tavily"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key if api_key is not None else settings.TAVILY_API_KEY

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    async def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        if not self._api_key:
            raise IntegrationError("TAVILY_API_KEY is not set")
        payload = {
            "api_key": self._api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
            "include_answer": False,
            "include_raw_content": False,
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(_ENDPOINT, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise IntegrationError(f"Tavily search failed: {exc}") from exc

        results: list[SearchResult] = []
        for item in data.get("results", [])[:max_results]:
            url = item.get("url", "")
            results.append(
                SearchResult(
                    title=item.get("title") or url,
                    url=url,
                    snippet=item.get("content") or "",
                    published=item.get("published_date"),
                    score=item.get("score"),
                )
            )
        return results
