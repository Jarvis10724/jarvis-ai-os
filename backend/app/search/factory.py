"""
Single entry point for getting the configured web-search provider.

`SEARCH_PROVIDER` in config picks the vendor ("" disables search entirely;
"tavily" for live; "mock" for offline dev/testing). Returns None whenever
search is unavailable (no provider selected, unknown name, or a real provider
whose key is missing) so callers degrade gracefully instead of erroring.
"""
from __future__ import annotations

import importlib
from functools import lru_cache

from app.config import settings
from app.logging_config import get_logger
from app.search.base import BaseSearchProvider

logger = get_logger(__name__)

_PROVIDER_REGISTRY = {
    "tavily": "app.search.tavily_provider.TavilyProvider",
    "mock": "app.search.mock_provider.MockSearchProvider",
}


def _import_class(dotted_path: str):
    module_path, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


@lru_cache
def _build(name: str) -> BaseSearchProvider | None:
    dotted = _PROVIDER_REGISTRY.get(name)
    if dotted is None:
        logger.warning("unknown_search_provider", provider=name, available=list(_PROVIDER_REGISTRY))
        return None
    try:
        return _import_class(dotted)()
    except Exception as exc:  # noqa: BLE001
        logger.error("search_provider_init_failed", provider=name, error=str(exc))
        return None


def get_search_provider() -> BaseSearchProvider | None:
    """The active search provider, or None if search isn't configured/available."""
    name = (settings.SEARCH_PROVIDER or "").strip().lower()
    if not name:
        return None
    provider = _build(name)
    if provider is None or not provider.configured:
        return None
    return provider


def search_configured() -> bool:
    return get_search_provider() is not None


def reset_cache() -> None:
    """Drop the memoized provider (used by tests that flip SEARCH_PROVIDER)."""
    _build.cache_clear()
