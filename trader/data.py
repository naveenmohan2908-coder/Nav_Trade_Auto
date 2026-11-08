"""Market data from Alpaca (free IEX feed, which is what paper-only accounts get)."""
from datetime import datetime, timedelta, timezone

import pandas as pd
from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from . import config

NY = "America/New_York"


def make_data_client() -> StockHistoricalDataClient:
    return StockHistoricalDataClient(config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY)


def get_daily_bars(client, symbols, days: int) -> dict[str, pd.DataFrame]:
    """Daily bars per symbol, adjusted for splits/dividends."""
    start = datetime.now(timezone.utc) - timedelta(days=days)
    request = StockBarsRequest(
        symbol_or_symbols=list(symbols),
        timeframe=TimeFrame.Day,
        start=start,
        feed=DataFeed.IEX,
        adjustment=Adjustment.ALL,
    )
    df = client.get_stock_bars(request).df
    bars: dict[str, pd.DataFrame] = {}
    if df.empty:
        return bars
    available = set(df.index.get_level_values("symbol"))
    for sym in symbols:
        if sym in available:
            s = df.xs(sym, level="symbol").copy()
            s.index = pd.to_datetime(s.index)
            bars[sym] = s
    return bars


def drop_unfinished_today(df: pd.DataFrame) -> pd.DataFrame:
    """While the market is open, today's daily bar is incomplete. Signals use finished days only."""
    today_ny = pd.Timestamp.now(tz=NY).date()
    bar_dates = df.index.tz_convert(NY).date
    return df[bar_dates < today_ny]
