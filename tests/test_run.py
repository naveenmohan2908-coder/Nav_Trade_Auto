"""End-to-end test of trader.main.run() with a fake broker and fake data. No network needed."""
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from trader import ai_filter, broker, config, data, main, news

IDX = pd.date_range("2025-01-01", periods=160, freq="B", tz="UTC")
I = np.arange(160)


def frame(close):
    return pd.DataFrame({"close": close}, index=IDX)


UP = frame(100 + 0.3 * I + 4 * np.sin((I + 4) / 3))    # uptrend that ends on a pullback (RSI ~52)
DOWN = frame(200 - 0.3 * I - 2.5 * np.sin(I / 3))      # steady downtrend
HOT = frame(100 + 0.3 * I + 2.5 * np.sin(I / 3))       # uptrend but overbought (RSI ~80)


class Fake:
    def __init__(self, positions=None, equity=100_000, last_equity=100_000, cash=100_000):
        self.orders, self.closed = [], []
        self.positions = positions or {}
        self.account = SimpleNamespace(equity=str(equity), last_equity=str(last_equity), cash=str(cash))


@pytest.fixture
def env(monkeypatch):
    fake = Fake()
    monkeypatch.setattr(config, "ALPACA_API_KEY", "k")
    monkeypatch.setattr(config, "ALPACA_SECRET_KEY", "s")
    monkeypatch.setattr(config, "SYMBOLS", ("UPSTOCK", "DOWNSTOCK"))
    monkeypatch.setattr(config, "DRY_RUN", False)
    monkeypatch.setattr(config, "USE_AI_FILTER", False)
    monkeypatch.setattr(main, "write_outputs", lambda d: None)
    monkeypatch.setattr(data, "make_data_client", lambda: None)
    monkeypatch.setattr(data, "get_daily_bars", lambda c, s, d: {"UPSTOCK": UP, "DOWNSTOCK": DOWN})
    monkeypatch.setattr(broker, "make_client", lambda: SimpleNamespace(get_account=lambda: fake.account))
    monkeypatch.setattr(broker, "market_is_open", lambda c: True)
    monkeypatch.setattr(broker, "get_positions", lambda c: fake.positions)
    monkeypatch.setattr(broker, "buy_notional", lambda c, sym, usd: (fake.orders.append((sym, usd)), SimpleNamespace(id="abcdef123456"))[1])
    monkeypatch.setattr(broker, "close_position", lambda c, sym: fake.closed.append(sym))
    return fake


def test_buys_uptrend_and_ignores_downtrend(env):
    assert main.run() == 0
    assert env.orders == [("UPSTOCK", 10_000.0)]   # 10% of equity
    assert env.closed == []


def test_sells_held_position_when_trend_turns_down(env):
    env.positions = {"DOWNSTOCK": SimpleNamespace(unrealized_plpc="0.01")}
    main.run()
    assert env.closed == ["DOWNSTOCK"]


def test_stop_loss_closes_even_in_uptrend(env):
    env.positions = {"UPSTOCK": SimpleNamespace(unrealized_plpc="-0.10")}
    main.run()
    assert env.closed == ["UPSTOCK"]
    assert env.orders == []


def test_does_not_double_buy_held_position(env):
    env.positions = {"UPSTOCK": SimpleNamespace(unrealized_plpc="0.02")}
    main.run()
    assert env.orders == [] and env.closed == []


def test_dry_run_places_nothing(env, monkeypatch):
    monkeypatch.setattr(config, "DRY_RUN", True)
    env.positions = {"DOWNSTOCK": SimpleNamespace(unrealized_plpc="0.01")}
    main.run()
    assert env.orders == [] and env.closed == []


def test_daily_loss_limit_blocks_buys(env):
    env.account = SimpleNamespace(equity="95000", last_equity="100000", cash="95000")
    main.run()
    assert env.orders == []


def test_max_positions_blocks_buys(env, monkeypatch):
    monkeypatch.setattr(config, "MAX_OPEN_POSITIONS", 1)
    env.positions = {"OTHER": SimpleNamespace(unrealized_plpc="0.0")}
    main.run()
    assert env.orders == []


def test_ai_veto_blocks_buy_and_approval_allows(env, monkeypatch):
    monkeypatch.setattr(config, "USE_AI_FILTER", True)
    monkeypatch.setattr(news, "get_headlines", lambda s: ["Company under fraud investigation"])
    monkeypatch.setattr(ai_filter, "review_buy", lambda s, i, h: {"approve": False, "reason": "fraud probe"})
    main.run()
    assert env.orders == []
    monkeypatch.setattr(ai_filter, "review_buy", lambda s, i, h: {"approve": True, "reason": "ok"})
    main.run()
    assert env.orders == [("UPSTOCK", 10_000.0)]


def test_market_closed_does_nothing(env, monkeypatch):
    monkeypatch.setattr(broker, "market_is_open", lambda c: False)
    assert main.run() == 0
    assert env.orders == [] and env.closed == []


def test_ai_failure_fails_closed(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "bad-key")
    # No network in tests -> the API call raises -> must veto, not approve
    verdict = ai_filter.review_buy("AAPL", {"price": 1}, [])
    assert verdict["approve"] is False


def test_overbought_uptrend_is_not_bought(env, monkeypatch):
    monkeypatch.setattr(data, "get_daily_bars", lambda c, s, d: {"UPSTOCK": HOT, "DOWNSTOCK": DOWN})
    main.run()
    assert env.orders == []
