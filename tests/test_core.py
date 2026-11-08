import numpy as np
import pandas as pd

from trader import risk, strategy
from trader.backtest import backtest_symbol


def make_prices(n=200, drift=0.001, seed=1):
    rng = np.random.default_rng(seed)
    close = 100 * np.cumprod(1 + rng.normal(drift, 0.01, n))
    idx = pd.date_range("2024-01-01", periods=n, freq="B", tz="UTC")
    return pd.DataFrame({"close": close}, index=idx)


def test_rsi_bounds():
    r = strategy.rsi(make_prices()["close"]).dropna()
    assert ((r >= 0) & (r <= 100)).all()


def test_rsi_all_up_is_100():
    close = pd.Series(np.arange(1.0, 60.0))
    assert strategy.rsi(close).iloc[-1] == 100


def test_next_state_rules():
    assert strategy.next_state(False, True, 50, 75) is True      # enter
    assert strategy.next_state(False, True, 80, 75) is False     # overbought -> don't enter
    assert strategy.next_state(False, False, 50, 75) is False    # no trend
    assert strategy.next_state(True, True, 90, 75) is True       # RSI filter only gates entries
    assert strategy.next_state(True, False, 50, 75) is False     # exit
    assert strategy.next_state(False, True, float("nan"), 75) is False  # missing data -> stay flat


def test_no_position_before_indicators_exist():
    ind = strategy.add_indicators(make_prices(), 20, 50, 14)
    held = strategy.target_positions(ind, 75)
    assert not held.iloc[:49].any()


def test_risk_rules():
    assert risk.daily_loss_exceeded(96_000, 100_000, 0.03) is True
    assert risk.daily_loss_exceeded(99_000, 100_000, 0.03) is False
    assert risk.position_size(100_000, 100_000, 0.10) == 10_000
    assert risk.position_size(100_000, 5_000, 0.10) == 4_750      # cash-limited
    assert risk.position_size(100_000, 0, 0.10) == 0
    assert risk.stop_loss_hit(-0.08, 0.07) is True
    assert risk.stop_loss_hit(-0.02, 0.07) is False


def test_backtest_runs_and_has_sane_numbers():
    res = backtest_symbol(make_prices(400))
    assert -1 < res["strategy_return"] < 10
    assert -1 <= res["strategy_max_dd"] <= 0
    assert 0 <= res["time_in_market"] <= 1
