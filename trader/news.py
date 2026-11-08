"""Recent headlines for a symbol (Alpaca news API). Best effort: returns [] on any failure."""
import logging

from alpaca.data.historical.news import NewsClient
from alpaca.data.requests import NewsRequest

from . import config

log = logging.getLogger(__name__)


def get_headlines(symbol: str, limit: int = 8) -> list[str]:
    try:
        client = NewsClient(config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY)
        result = client.get_news(NewsRequest(symbols=symbol, limit=limit))
        items = getattr(result, "data", {}).get("news", [])
        return [str(item.headline) for item in items][:limit]
    except Exception as exc:  # news is a nice-to-have, never break trading over it
        log.warning("Could not fetch news for %s: %s", symbol, exc)
        return []
