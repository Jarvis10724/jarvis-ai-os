"""Live market data for the Investment Dashboard — Finnhub-backed quotes and
per-symbol company news. Every function degrades gracefully to an empty
result when FINNHUB_API_KEY isn't set, rather than raising, so callers can
render an honest "not configured" state instead of a 500.
"""
import time
from datetime import date, timedelta

import httpx

from app.config import settings

_CACHE_TTL_SECONDS = 45
_quote_cache: dict[str, tuple[float, dict]] = {}
_news_cache: dict[str, tuple[float, list[dict]]] = {}

# Finnhub's free tier has no clean "spot" quote for some watchlist staples —
# crypto needs an exchange-prefixed symbol, and there's no spot-gold ticker,
# so GOLD maps to the GLD ETF as an honest, clearly-labeled proxy rather than
# faking a spot price.
SYMBOL_ALIASES: dict[str, str] = {
    "BTC": "BINANCE:BTCUSDT",
    "ETH": "BINANCE:ETHUSDT",
    "GOLD": "GLD",
}


def is_configured() -> bool:
    return bool(settings.FINNHUB_API_KEY)


async def _get_json(client: httpx.AsyncClient, path: str, params: dict):
    resp = await client.get(
        f"https://finnhub.io/api/v1{path}",
        params={**params, "token": settings.FINNHUB_API_KEY},
        timeout=8.0,
    )
    resp.raise_for_status()
    return resp.json()


async def get_quotes(symbols: list[str]) -> list[dict]:
    """One quote dict per requested symbol, always — a per-symbol failure
    (bad ticker, rate limit) reports {"error": "unavailable"} for that
    symbol rather than failing the whole batch."""
    if not is_configured() or not symbols:
        return []

    now = time.monotonic()
    results: list[dict] = []
    async with httpx.AsyncClient() as client:
        for raw_symbol in symbols:
            symbol = raw_symbol.strip().upper()
            if not symbol:
                continue
            cached = _quote_cache.get(symbol)
            if cached and now - cached[0] < _CACHE_TTL_SECONDS:
                results.append(cached[1])
                continue
            lookup_symbol = SYMBOL_ALIASES.get(symbol, symbol)
            try:
                data = await _get_json(client, "/quote", {"symbol": lookup_symbol})
                price = data.get("c")
                if not price:
                    raise ValueError("no price data")
                quote = {
                    "symbol": symbol,
                    "lookup_symbol": lookup_symbol,
                    "price": price,
                    "change": data.get("d") or 0,
                    "change_percent": data.get("dp") or 0,
                    "error": None,
                }
            except Exception:
                quote = {
                    "symbol": symbol,
                    "lookup_symbol": lookup_symbol,
                    "price": None,
                    "change": None,
                    "change_percent": None,
                    "error": "unavailable",
                }
            _quote_cache[symbol] = (now, quote)
            results.append(quote)
    return results


async def get_news(symbols: list[str], limit_per_symbol: int = 3) -> list[dict]:
    """Real per-symbol company news from the last 7 days. Aliased symbols
    (crypto, the gold ETF proxy) are skipped — Finnhub's free company-news
    endpoint only covers plain equities."""
    if not is_configured() or not symbols:
        return []

    today = date.today()
    week_ago = today - timedelta(days=7)
    now = time.monotonic()
    headlines: list[dict] = []
    async with httpx.AsyncClient() as client:
        for raw_symbol in symbols:
            symbol = raw_symbol.strip().upper()
            if not symbol:
                continue
            lookup_symbol = SYMBOL_ALIASES.get(symbol, symbol)
            if ":" in lookup_symbol:
                continue
            cached = _news_cache.get(symbol)
            if cached and now - cached[0] < _CACHE_TTL_SECONDS:
                headlines.extend(cached[1])
                continue
            try:
                data = await _get_json(
                    client, "/company-news", {"symbol": lookup_symbol, "from": str(week_ago), "to": str(today)}
                )
                items = [
                    {
                        "id": str(item.get("id")),
                        "symbol": symbol,
                        "headline": item.get("headline"),
                        "summary": item.get("summary"),
                        "url": item.get("url"),
                        "source": item.get("source"),
                        "datetime": item.get("datetime"),
                    }
                    for item in (data or [])[:limit_per_symbol]
                ]
            except Exception:
                items = []
            _news_cache[symbol] = (now, items)
            headlines.extend(items)
    headlines.sort(key=lambda h: h.get("datetime") or 0, reverse=True)
    return headlines
