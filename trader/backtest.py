"""Replay the strategy on history.   python -m trader.backtest [years]

Needs ALPACA_API_KEY / ALPACA_SECRET_KEY (reads data only, places no orders).
Caveats: no slippage model, fixed cost per trade, and a good result here proves very little.
"""
import sys

import pandas as pd

from . import config, data, strategy

COST_PER_TRADE = 0.0005  # 0.05% each time we enter or exit (rough allowance for spread/slippage)


def backtest_symbol(df: pd.DataFrame) -> dict:
    ind = strategy.add_indicators(df, config.FAST_SMA, config.SLOW_SMA, config.RSI_PERIOD)
    held = strategy.target_positions(ind, config.RSI_MAX_ENTRY).astype(float)

    daily_ret = ind["close"].pct_change().fillna(0.0)
    exposure = held.shift(1).fillna(0.0)  # decide at today's close, earn tomorrow's return
    trades = exposure.diff().abs().fillna(exposure.abs())
    strat_ret = daily_ret * exposure - trades * COST_PER_TRADE

    def stats(returns: pd.Series) -> tuple[float, float]:
        curve = (1 + returns).cumprod()
        return curve.iloc[-1] - 1, (curve / curve.cummax() - 1).min()

    s_total, s_dd = stats(strat_ret)
    b_total, b_dd = stats(daily_ret)
    return {
        "strategy_return": s_total, "strategy_max_dd": s_dd,
        "buy_hold_return": b_total, "buy_hold_max_dd": b_dd,
        "trades": int(trades.sum()), "time_in_market": float(exposure.mean()),
    }


def main() -> None:
    years = float(sys.argv[1]) if len(sys.argv) > 1 else 3
    bars = data.get_daily_bars(data.make_data_client(), config.SYMBOLS, int(365 * years) + 120)
    rows = {sym: backtest_symbol(df) for sym, df in bars.items()}
    table = pd.DataFrame(rows).T
    pct = lambda x: f"{x:.1%}"  # noqa: E731
    for col in ("strategy_return", "strategy_max_dd", "buy_hold_return", "buy_hold_max_dd", "time_in_market"):
        table[col] = table[col].map(pct)
    print(f"\nBacktest over ~{years:g} years (daily bars, long-only)\n")
    print(table.to_string())
    print("\nIf the strategy doesn't beat (or at least cut the drawdown of) buy & hold, rethink it.")


if __name__ == "__main__":
    main()
