"""
Provider-agnostic interface for web search.

Mirrors the `app.ai_providers` pattern: nothing outside `app/search/` imports a
specific search vendor's SDK/HTTP shape. Swapping Tavily for Brave/SerpAPI/etc.
is a config change (`SEARCH_PROVIDER`) + one new `BaseSearchProvider` subclass,
never a change to the workspace or endpoint code that consumes results.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class SearchResult:
    """One retrieved web result, normalized across providers."""

    title: str
    url: str
    snippet: str
    source: str = ""            # publisher / domain
    published: str | None = None
    score: float | None = None

    def domain(self) -> str:
        if self.source:
            return self.source
        try:
            return urlparse(self.url).netloc or ""
        except ValueError:
            return ""

    def as_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.domain(),
            "published": self.published,
            "score": self.score,
        }

    def as_source(self, sid: str) -> dict:
        """Shape the workspace Sources panel expects (see workspace_actions
        deep_research state schema). `derived=False` marks it as a REAL
        retrieved page, not a model-recalled guess."""
        return {
            "id": sid,
            "title": self.title or self.url,
            "url": self.url,
            "kind": "web",
            "note": (self.snippet or "")[:500],
            "source": self.domain(),
            "published": self.published,
            "derived": False,
        }


class BaseSearchProvider(ABC):
    """Subclass per vendor. Keep the surface tiny and stable."""

    name: str = "base"

    @property
    def configured(self) -> bool:
        """Whether this provider has what it needs (API key, etc.) to run."""
        return True

    @abstractmethod
    async def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        """Return normalized results for a query, best-first."""
        raise NotImplementedError
