from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser
from app.core import market_data_service

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/quotes")
async def get_quotes(
    current_user: CurrentUser,
    symbols: str = Query(..., description="Comma-separated ticker symbols, e.g. SPY,BTC,AAPL"),
):
    symbol_list = [s for s in (s.strip() for s in symbols.split(",")) if s]
    configured = market_data_service.is_configured()
    quotes = await market_data_service.get_quotes(symbol_list) if configured else []
    return {"configured": configured, "quotes": quotes}


@router.get("/news")
async def get_news(
    current_user: CurrentUser,
    symbols: str = Query(..., description="Comma-separated ticker symbols, e.g. SPY,AAPL"),
    limit_per_symbol: int = Query(3, le=10),
):
    symbol_list = [s for s in (s.strip() for s in symbols.split(",")) if s]
    configured = market_data_service.is_configured()
    headlines = await market_data_service.get_news(symbol_list, limit_per_symbol) if configured else []
    return {"configured": configured, "headlines": headlines}
