"""Entry point:  python -m trader.main

One run = one pass: check market -> check risk -> read signals -> sell -> buy -> log.
Designed to be run on a schedule (GitHub Actions) with daily bars.
"""
import csv
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import ai_filter, broker, config, data, news, risk, strategy

log = logging.getLogger("trader")
LOG_DIR = Path("logs")
FIELDS = ["time_utc", "symbol", "action", "detail", "price", "rsi", "sma_fast", "sma_slow"]


def record(decisions: list, symbol: str, action: str, detail: str, snap: dict | None = None) -> None:
    snap = snap or {}
    decisions.append(
        {
            "time_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
            "action": action,
            "detail": detail,
            "price": snap.get("price", ""),
            "rsi": snap.get("rsi", ""),
            "sma_fast": snap.get("sma_fast", ""),
            "sma_slow": snap.get("sma_slow", ""),
        }
    )
    log.info("%-5s %-8s %s", symbol, action, detail)


def write_outputs(decisions: list) -> None:
    if not decisions:
        return
    LOG_DIR.mkdir(exist_ok=True)
    path = LOG_DIR / "decisions.csv"
    new_file = not path.exists()
    with path.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerows(decisions)

    # Pretty table on the GitHub Actions run page
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        lines = ["### Paper trader decisions", "", "| Symbol | Action | Detail | Price | RSI |", "|---|---|---|---|---|"]
        for d in decisions:
            lines.append(f"| {d['symbol']} | {d['action']} | {d['detail']} | {d['price']} | {d['rsi']} |")
        with open(summary_path, "a") as f:
            f.write("\n".join(lines) + "\n")


def run() -> int:
    if not (config.ALPACA_API_KEY and config.ALPACA_SECRET_KEY):
        log.error("Missing ALPACA_API_KEY / ALPACA_SECRET_KEY environment variables.")
        return 1

    trading = broker.make_client()
    log.info(
        "PAPER trading | dry_run=%s | ai_filter=%s | symbols=%s",
        config.DRY_RUN, config.USE_AI_FILTER, ",".join(config.SYMBOLS),
    )

    if not broker.market_is_open(trading):
        log.info("Market is closed (weekend/holiday/after hours). Nothing to do.")
        return 0

    account = trading.get_account()
    equity, last_equity, cash = float(account.equity), float(account.last_equity), float(account.cash)
    positions = broker.get_positions(trading)
    log.info("Equity $%.2f | cash $%.2f | open positions: %d", equity, cash, len(positions))

    halt_buys = risk.daily_loss_exceeded(equity, last_equity, config.DAILY_LOSS_LIMIT_PCT)
    if halt_buys:
        log.warning("Daily loss limit hit (equity $%.2f vs $%.2f). No new buys today.", equity, last_equity)

    for sym in positions:
        if sym not in config.SYMBOLS:
            log.warning("Holding %s which is outside the SYMBOLS universe; the bot will ignore it.", sym)

    bars = data.get_daily_bars(data.make_data_client(), config.SYMBOLS, config.HISTORY_DAYS)
    decisions: list = []
    sells: list = []
    buy_candidates: list = []

    # ---- 1. Read signals ----------------------------------------------------
    for sym in config.SYMBOLS:
        if sym not in bars:
            record(decisions, sym, "SKIP", "no price data returned")
            continue
        ind = strategy.add_indicators(
            data.drop_unfinished_today(bars[sym]), config.FAST_SMA, config.SLOW_SMA, config.RSI_PERIOD
        )
        if len(ind) < config.SLOW_SMA + 1:
            record(decisions, sym, "SKIP", "not enough history for indicators")
            continue

        row = ind.iloc[-1]
        snap = {
            "price": round(float(row["close"]), 2),
            "rsi": round(float(row["rsi"]), 1),
            "sma_fast": round(float(row["sma_fast"]), 2),
            "sma_slow": round(float(row["sma_slow"]), 2),
            "momentum_20d": round(float(row["momentum_20d"]), 3),
        }
        held = sym in positions

        if held and risk.stop_loss_hit(float(positions[sym].unrealized_plpc), config.STOP_LOSS_PCT):
            sells.append((sym, f"stop-loss ({float(positions[sym].unrealized_plpc):.1%})", snap))
            continue

        want = strategy.next_state(held, row["trend_up"], row["rsi"], config.RSI_MAX_ENTRY)
        if held and not want:
            sells.append((sym, "trend turned down", snap))
        elif held:
            record(decisions, sym, "HOLD", "trend still up", snap)
        elif want:
            buy_candidates.append((snap["momentum_20d"], sym, snap))
        else:
            record(decisions, sym, "WAIT", "no entry signal", snap)

    # ---- 2. Sells first (frees up slots) -----------------------------------
    sold = 0
    for sym, why, snap in sells:
        try:
            if not config.DRY_RUN:
                broker.close_position(trading, sym)
            record(decisions, sym, "SELL" + (" (dry)" if config.DRY_RUN else ""), why, snap)
            sold += 1
        except Exception as exc:
            record(decisions, sym, "ERROR", f"sell failed: {exc}", snap)

    # ---- 3. Buys, strongest momentum first ---------------------------------
    slots = config.MAX_OPEN_POSITIONS - (len(positions) - sold)
    cash_left = cash
    for _, sym, snap in sorted(buy_candidates, key=lambda c: c[0], reverse=True):
        if halt_buys:
            record(decisions, sym, "SKIP", "daily loss limit reached", snap)
            continue
        if slots <= 0:
            record(decisions, sym, "SKIP", "max open positions reached", snap)
            continue
        size = risk.position_size(equity, cash_left, config.MAX_POSITION_PCT)
        if size < config.MIN_ORDER_USD:
            record(decisions, sym, "SKIP", f"not enough cash (${size:.2f})", snap)
            continue
        if config.USE_AI_FILTER:
            verdict = ai_filter.review_buy(sym, snap, news.get_headlines(sym))
            if not verdict["approve"]:
                record(decisions, sym, "SKIP", f"AI veto: {verdict['reason']}", snap)
                continue
        try:
            if not config.DRY_RUN:
                order = broker.buy_notional(trading, sym, size)
                detail = f"bought ${size:.2f} (order {str(order.id)[:8]})"
            else:
                detail = f"would buy ${size:.2f}"
            record(decisions, sym, "BUY" + (" (dry)" if config.DRY_RUN else ""), detail, snap)
            cash_left -= size
            slots -= 1
        except Exception as exc:
            record(decisions, sym, "ERROR", f"buy failed: {exc}", snap)

    write_outputs(decisions)
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        return run()
    except Exception:
        log.exception("Run failed")
        return 1  # non-zero exit => GitHub Actions marks the run failed and emails you


if __name__ == "__main__":
    sys.exit(main())
