"""Thin wrapper around Alpaca's trading API. PAPER ONLY: paper=True is hard-coded on purpose."""
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

from . import config


def make_client() -> TradingClient:
    # Hard-coded paper=True. Going live should be a deliberate code change, not a config typo.
    return TradingClient(config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY, paper=True)


def market_is_open(client: TradingClient) -> bool:
    return bool(client.get_clock().is_open)


def get_positions(client: TradingClient) -> dict:
    return {p.symbol: p for p in client.get_all_positions()}


def buy_notional(client: TradingClient, symbol: str, dollars: float):
    """Market buy for a dollar amount (fractional shares)."""
    order = MarketOrderRequest(
        symbol=symbol, notional=round(dollars, 2), side=OrderSide.BUY, time_in_force=TimeInForce.DAY
    )
    return client.submit_order(order)


def close_position(client: TradingClient, symbol: str):
    return client.close_position(symbol)
