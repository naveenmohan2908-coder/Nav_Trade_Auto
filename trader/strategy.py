"""Trading rules. Pure functions on pandas data, so they're easy to test and backtest.

Rules (long-only):
  * Trend is UP when price > slow SMA and fast SMA > slow SMA.
  * If flat: open a position when the trend is UP and RSI isn't overbought.
  * If holding: stay in while the trend is UP, exit when it isn't.
"""
import pandas as pd


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's Relative Strength Index."""
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = gain / loss
    return 100 - 100 / (1 + rs)


def add_indicators(df: pd.DataFrame, fast: int, slow: int, rsi_period: int) -> pd.DataFrame:
    out = df.copy()
    out["sma_fast"] = out["close"].rolling(fast).mean()
    out["sma_slow"] = out["close"].rolling(slow).mean()
    out["rsi"] = rsi(out["close"], rsi_period)
    out["momentum_20d"] = out["close"].pct_change(20)
    out["trend_up"] = (out["close"] > out["sma_slow"]) & (out["sma_fast"] > out["sma_slow"])
    return out


def next_state(held: bool, trend_up: bool, rsi_value: float, rsi_max_entry: float) -> bool:
    """Should we be holding after seeing today's bar? One rule, used by live bot and backtest."""
    if held:
        return bool(trend_up)
    return bool(trend_up) and bool(rsi_value <= rsi_max_entry)  # NaN compares False -> stay flat


def target_positions(df: pd.DataFrame, rsi_max_entry: float) -> pd.Series:
    """Run the state machine over a whole history (used by the backtest)."""
    held = False
    states = []
    for up, r in zip(df["trend_up"], df["rsi"]):
        held = next_state(held, up, r, rsi_max_entry)
        states.append(held)
    return pd.Series(states, index=df.index, name="held")
