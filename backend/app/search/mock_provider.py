"""
Deterministic offline search provider — for DEV/TESTING the live-research
pipeline without a real API key. Enabled only when `SEARCH_PROVIDER=mock`.

Results are stable functions of the query and clearly labelled as mock
(example.com URLs), so the wiring (retrieval -> sources -> citations -> cache)
can be exercised end-to-end offline. Not for production use: with a real
provider unset, Deep Research stays in its honest model-knowledge mode instead.
"""
from __future__ import annotations

from app.search.base import BaseSearchProvider, SearchResult


class MockSearchProvider(BaseSearchProvider):
    name = "mock"

    @property
    def configured(self) -> bool:
        return True

    async def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        q = query.strip()
        slug = (q.lower().replace(" ", "-") or "topic")[:48]
        n = max(1, min(max_results, 5))
        return [
            SearchResult(
                title=f"{q.title()} — Reference {i}",
                url=f"https://example.com/{slug}/ref-{i}",
                snippet=(
                    f"Mock search result {i} for '{q}'. Deterministic offline data "
                    "for pipeline testing — replace with a real provider for production."
                ),
                source="example.com",
                score=round(1.0 - (i - 1) * 0.12, 2),
            )
            for i in range(1, n + 1)
        ]
